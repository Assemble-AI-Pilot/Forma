"""OAuth 2.0 Authorization Code + PKCE against Autodesk Platform Services.

The APS app is a public client — Desktop/Mobile/SPA — so there is no client
secret anywhere in this repo or on any user's machine. Five steps:

  1. Invent a random code_verifier; send Autodesk only its SHA-256 fingerprint
     (code_challenge, method S256).
  2. Bind a one-shot loopback listener on 127.0.0.1:8080. Not reachable from
     outside the machine.
  3. The user signs into Autodesk and approves the consent screen.
  4. Autodesk redirects to the listener with a one-time code. We check `state`
     matches what we sent (CSRF defence) and shut the listener down.
  5. Exchange code + code_verifier for tokens. Autodesk hashes the verifier and
     compares. No secret is transmitted or stored, because none exists.

PKCE changes *how* a token is obtained, never *what it can do*. The resulting
token is identical in capability to one obtained with a client secret. The
benefit is operational: nothing confidential to distribute, rotate or leak,
which matters because several people are meant to run this on their own
machines.

Standard library only, so there is nothing to pip install.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from typing import Any

from . import config

# Refresh a little early so a long call cannot expire mid-flight.
_EXPIRY_SKEW_SECONDS = 120


def _friendly(seconds: int) -> str:
    """Say '90 seconds' rather than '1 minutes'."""
    if seconds < 90:
        return f"{seconds} seconds"
    return f"{round(seconds / 60)} minutes"


class AuthError(RuntimeError):
    """Authentication or token-exchange failure."""


def log(message: str) -> None:
    """Diagnostics go to stderr. stdout carries MCP protocol frames and nothing
    else — one stray print() there corrupts the stream and the client reports an
    opaque parse failure."""
    print(f"[forma-auth] {message}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- PKCE


def _b64url(raw: bytes) -> str:
    """Base64url-encode without padding (RFC 7636)."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def new_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using the S256 method.

    48 random bytes base64url-encodes to 64 characters, inside the 43-128
    character range the spec requires.
    """
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


# ------------------------------------------------------------------ token storage


def protect_file(path) -> str:
    """Restrict a file to the current user. Returns what was actually achieved.

    POSIX mode bits are a no-op on Windows — os.chmod(0o600) there silently does
    nothing useful, so a plugin that calls it and moves on is telling itself a
    comforting story about a refresh token sitting in a readable file.

    On Windows the equivalent is an ACL, applied with icacls: strip inheritance,
    then grant only the current user. If that fails we say so rather than pretend.
    """
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
            return "posix mode 0600"
        except OSError as exc:
            return f"could not set mode 0600: {exc}"

    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if not user:
        return "WINDOWS: could not determine the current user; file is NOT restricted"
    try:
        import subprocess

        result = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0:
            return f"windows ACL: {user} only"
        return f"WINDOWS: icacls failed ({result.returncode}); file is NOT restricted"
    except Exception as exc:  # noqa: BLE001
        return f"WINDOWS: could not apply an ACL ({type(exc).__name__}); file is NOT restricted"


def _write_tokens(payload: dict[str, Any]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Create with 0600 from the outset rather than chmod-ing after writing, which
    # would briefly leave the refresh token world-readable. On Windows the mode is
    # ignored and protect_file() applies an ACL instead.
    fd = os.open(config.TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    protection = protect_file(config.TOKEN_FILE)
    if protection.startswith("WINDOWS"):
        log(protection)


def _read_tokens() -> dict[str, Any] | None:
    try:
        with open(config.TOKEN_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    """Record when the access token stops being usable.

    Autodesk returns expires_in (seconds from now), not an absolute time, so an
    absolute one is computed and stored.
    """
    payload = dict(payload)
    payload["obtained_at"] = int(time.time())
    payload["expires_at"] = int(time.time()) + int(payload.get("expires_in", 3600))
    return payload


# ------------------------------------------------------------------ token requests


def _post_token(form: dict[str, str]) -> dict[str, Any]:
    """Exchange or refresh, always as a PUBLIC client.

    client_id goes in the REQUEST BODY and there is NO HTTP Basic header. Sending
    Basic auth the way a confidential client would fails with
    `403 AUTH-001 "The client_id specified does not have access to the api
    product"` — a misleading message that suggests the app is misconfigured
    rather than the request being malformed. See FORMA-API-KEY.md §7.11.
    """
    body = urllib.parse.urlencode({**form, "client_id": config.CLIENT_ID}).encode()
    request = urllib.request.Request(
        config.TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": config.USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise AuthError(f"Token request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"Could not reach {config.TOKEN_URL}: {exc.reason}") from exc


# ------------------------------------------------------------------------- sign-in

_SUCCESS_PAGE = (
    b"<html><body style='font-family:system-ui;padding:3rem;text-align:center'>"
    b"<h2>Signed in to Forma.</h2>"
    b"<p>You can close this tab and return to Claude Code.</p>"
    b"</body></html>"
)

_FAILURE_PAGE = (
    b"<html><body style='font-family:system-ui;padding:3rem;text-align:center'>"
    b"<h2>Sign-in failed.</h2>"
    b"<p>Return to Claude Code for the error.</p>"
    b"</body></html>"
)


def login(scope: str | None = None, open_browser: bool = True,
          timeout_seconds: int = 300) -> dict[str, Any]:
    """Run the interactive sign-in and store the resulting tokens.

    Returns the stored token payload. Raises AuthError on any failure.
    """
    scope = scope or config.SCOPES
    verifier, challenge = new_pkce_pair()
    state = _b64url(secrets.token_bytes(16))
    captured: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - required name
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != config.REDIRECT_PATH:
                self.send_response(404)
                self.end_headers()
                return
            query = urllib.parse.parse_qs(parsed.query)
            captured.update({k: v[0] for k, v in query.items()})
            ok = "code" in captured and "error" not in captured
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_SUCCESS_PAGE if ok else _FAILURE_PAGE)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *args: Any) -> None:
            """Silence BaseHTTPRequestHandler's own stderr logging."""

    params = {
        "response_type": "code",
        "client_id": config.CLIENT_ID,
        "redirect_uri": config.REDIRECT_URI,
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = config.AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)

    try:
        server = http.server.HTTPServer(("127.0.0.1", config.REDIRECT_PORT), Handler)
    except OSError as exc:
        raise AuthError(
            f"Could not start the sign-in listener on port {config.REDIRECT_PORT}.\n\n"
            f"  {exc}\n\n"
            "Something else on this machine is already using that port. The Autodesk "
            f"app registers exactly one callback URL — {config.REDIRECT_URI} — so the "
            "port cannot be changed here; it would have to be changed in Autodesk too.\n\n"
            "Usual culprits: a local web server, another copy of this sign-in already "
            "running, or a development tool.\n"
            "  Windows:  netstat -ano | findstr :8080     then end that PID in Task Manager\n"
            "  macOS:    lsof -i :8080                    then kill that process"
        ) from exc

    # The consent screen is the step people get stuck on, so say plainly what is
    # about to happen, which account to use, and what to click.
    banner = [
        "",
        "=" * 68,
        "  SIGN IN TO AUTODESK",
        "=" * 68,
        "",
        "  A browser window should open now.",
        "",
        "  1. Sign in with your ASSEMBLE Autodesk account — the same one you",
        "     use for Forma. If a different account is already signed in, sign",
        "     out first or use a private window.",
        "",
        "  2. Autodesk will ask you to allow 'Assemble Claude Forma MCP' to",
        "     access your data. Click ALLOW. You will only see this once.",
        "",
        "  3. The page will say 'Signed in to Forma'. You can close that tab.",
        "",
        "  If the browser did NOT open, copy this link into it yourself:",
        "",
        f"  {authorize_url}",
        "",
        "=" * 68,
        f"  Waiting for you to finish… (up to {_friendly(timeout_seconds)})",
        "",
    ]
    print("\n".join(banner), file=sys.stderr, flush=True)

    opened = False
    if open_browser:
        try:
            opened = webbrowser.open(authorize_url)
        except Exception:  # noqa: BLE001 - a headless box has no browser; not fatal
            opened = False
    if not opened:
        log("could not open a browser automatically — use the link above")

    # serve_forever() never returns if the user closes the tab or walks away, and a
    # command that hangs with no explanation is worse than one that fails. Poll with
    # a deadline instead, so there is always an exit and always a reason.
    server.timeout = 1.0
    deadline = time.time() + timeout_seconds
    while not captured and time.time() < deadline:
        try:
            server.handle_request()
        except OSError:
            break
    server.server_close()

    if not captured:
        raise AuthError(
            f"Timed out after {_friendly(timeout_seconds)} — no response came back "
            "from the browser.\n\n"
            "Either the sign-in was not completed, or the browser could not reach "
            f"{config.REDIRECT_URI}.\n\n"
            "Try again with:  python login.py\n"
            "If a firewall prompt appeared when this started, allow Python to accept "
            "local connections."
        )

    if "error" in captured:
        raise AuthError(
            f"Autodesk returned {captured.get('error')}: "
            f"{captured.get('error_description', '')}"
        )
    # Reject a mismatched state rather than trusting the redirect. Without this an
    # injected code from elsewhere would be exchanged as if it were ours.
    if captured.get("state") != state:
        raise AuthError("State mismatch — aborting (possible cross-site request).")
    if "code" not in captured:
        raise AuthError(f"No authorisation code received. Got: {sorted(captured)}")

    tokens = _post_token(
        {
            "grant_type": "authorization_code",
            "code": captured["code"],
            "redirect_uri": config.REDIRECT_URI,
            "code_verifier": verifier,
        }
    )
    stored = _stamp(tokens)
    _write_tokens(stored)
    log(f"signed in; tokens at {config.TOKEN_FILE}")
    if not stored.get("refresh_token"):
        log("WARNING: no refresh token — was offline_access in the scopes?")
    return stored


def refresh() -> dict[str, Any]:
    """Renew the access token from the stored refresh token."""
    tokens = _read_tokens()
    if not tokens:
        raise AuthError("Not signed in. Run login first.")
    if not tokens.get("refresh_token"):
        raise AuthError("No refresh token stored — sign in again with offline_access.")

    form = {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]}
    # Autodesk's token response does not reliably include `scope`, so a stored
    # null there means "unknown", not "none granted" (§7.10). Only echo it back
    # when we actually have one.
    if tokens.get("scope"):
        form["scope"] = tokens["scope"]

    fresh = _stamp(_post_token(form))
    # A refresh response may omit the refresh token; keep the existing one so we
    # do not silently lose the ability to renew.
    fresh.setdefault("refresh_token", tokens["refresh_token"])
    fresh.setdefault("scope", tokens.get("scope"))
    _write_tokens(fresh)
    log("access token refreshed")
    return fresh


def get_access_token(interactive: bool = False) -> str:
    """Return a currently-valid access token, refreshing if needed.

    interactive=True permits a full browser sign-in; the MCP server passes False
    because a server has no business opening a browser mid-tool-call.
    """
    tokens = _read_tokens()
    if not tokens:
        if interactive:
            tokens = login()
        else:
            raise AuthError(
                "Not signed in to Forma. Run:\n"
                f'  python3 -c "from forma_mcp import auth; auth.login()"'
            )

    if int(tokens.get("expires_at", 0)) - _EXPIRY_SKEW_SECONDS > int(time.time()):
        return tokens["access_token"]

    try:
        return refresh()["access_token"]
    except AuthError:
        if interactive:
            return login()["access_token"]
        raise


# Autodesk's published lifetimes (APS OAuth v2): authorization code 5 minutes,
# access token 60 minutes, id token 60 minutes, REFRESH TOKEN 15 DAYS.
REFRESH_TOKEN_DAYS = 15


def status() -> dict[str, Any]:
    """Non-throwing summary of the stored credential, for orientation tools.

    THE HEADLINE IS `needs_sign_in`, NOT `authenticated`.

    An earlier version computed "authenticated" from the access token alone. That
    token lasts 60 minutes and the refresh token lasts 15 days, and refreshing is
    automatic and silent — so a completely healthy install reported
    `authenticated: false` for roughly 23 hours out of every 24, and offered a
    sign-in nobody needed.

    That is not merely untidy. When someone hits an unrelated failure, a status
    tool saying "not authenticated" is the most plausible-looking explanation in
    the room, and it sends them to re-authenticate instead of to the real cause.
    The equivalent mistake in the Aconex plugin cost several misdiagnosed installs.

    So: `authenticated` now means USABLE WITHOUT A HUMAN — a live access token, or
    a refresh token that can silently produce one. The 60-minute detail is still
    reported, but as diagnostics, never as the headline.
    """
    tokens = _read_tokens()
    if not tokens:
        return {
            "authenticated": False,
            "needs_sign_in": True,
            "token_file": str(config.TOKEN_FILE),
            "reason": "No token file. Nobody has signed in on this machine yet.",
            "fix": "python login.py",
        }

    remaining = int(tokens.get("expires_at", 0)) - int(time.time())
    access_live = remaining > 0
    refresh_available = bool(tokens.get("refresh_token"))

    # Estimated, not authoritative: Autodesk rotates the refresh token on every
    # use, so obtained_at moves forward each silent refresh. Reported as an
    # estimate rather than a promise.
    refresh_age = int(time.time()) - int(tokens.get("obtained_at") or 0)
    refresh_days_left = REFRESH_TOKEN_DAYS - (refresh_age / 86400)
    refresh_probably_valid = refresh_available and refresh_days_left > 0

    usable = access_live or refresh_probably_valid
    return {
        # The two fields anything should actually read.
        "authenticated": usable,
        "needs_sign_in": not usable,

        # Diagnostics. Never lead with these.
        "access_token_live": access_live,
        "refresh_available": refresh_available,
        "access_token_expires_in_minutes": round(remaining / 60, 1),
        "refresh_estimated_days_left": round(refresh_days_left, 1) if refresh_available else None,

        "token_file": str(config.TOKEN_FILE),
        "file_protection": protect_file(config.TOKEN_FILE),
        "scope_recorded": tokens.get("scope"),
        "scope_note": (
            "Autodesk's token response does not reliably include `scope`. "
            "A null here means unknown, not none — verify by making a call."
        ),
        "how_to_read_this": (
            "An expired ACCESS token is normal and is renewed silently; it lasts "
            "60 minutes while the refresh token lasts 15 days. Only `needs_sign_in` "
            "means a person has to do something. Do not offer a sign-in command "
            "unless it is true."
        ),
        "fix": None if usable else "python login.py",
    }


def logout() -> dict[str, Any]:
    """Delete the stored tokens. The APS app itself is untouched."""
    existed = config.TOKEN_FILE.exists()
    if existed:
        config.TOKEN_FILE.unlink()
    return {"removed": existed, "token_file": str(config.TOKEN_FILE)}


def whoami(token: str | None = None) -> dict[str, Any]:
    """Who the stored credential actually belongs to.

    Signing in with a personal or a previous employer's Autodesk account is an
    easy mistake and an invisible one: the plugin works perfectly, against the
    wrong person's permissions. Worth confirming once, out loud, after sign-in.

    Deliberately a different host to the rest of the API, so it does not go
    through client.request().
    """
    try:
        token = token or get_access_token()
    except AuthError as exc:
        return {"error": str(exc)}
    request = urllib.request.Request(
        "https://api.userprofile.autodesk.com/userinfo",
        headers={"Authorization": f"Bearer {token}", "User-Agent": config.USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT) as response:
            profile = json.load(response)
    except urllib.error.HTTPError as exc:
        return {"error": f"userinfo failed ({exc.code})"}
    except urllib.error.URLError as exc:
        return {"error": f"could not reach userinfo: {exc.reason}"}
    return {
        "name": profile.get("name"),
        "email": profile.get("email"),
        "autodesk_id": profile.get("sub"),
    }
