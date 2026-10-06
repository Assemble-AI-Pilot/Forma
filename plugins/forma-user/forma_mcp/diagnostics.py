"""Diagnostic capture, so a user who hits a problem can hand over one file.

Two ways in, because the obvious design fails in the case that matters most:

  * `forma_diagnostics`         a tool, for when the plugin runs but misbehaves
  * `python3 login.py diagnose` a command, for when the server will not start

If the plugin is broken badly enough to be worth reporting, the tool that reports
it may be broken too. The command path imports as little as possible and degrades
to a usable report even when almost everything else has failed.

WHAT GOES IN. Enough to diagnose without a screen share: versions, auth state,
configuration, the recent call history, and every failure with its Autodesk error
code and traceback.

WHAT NEVER GOES IN. Tokens, in any form. The report is written by redacting on the
way OUT rather than by trusting each call site to pass the right thing — anything
token-shaped is scrubbed from every string before it is written, including from
tracebacks and error bodies, which is exactly where a credential would otherwise
leak.

Record CONTENT is redacted by default too. A failure report needs the shape of the
data, not Assemble's commercial detail — so vendor names and amounts are dropped
unless the user deliberately asks to include them.
"""
from __future__ import annotations

import collections
import datetime
import json
import os
import platform
import re
import sys
import traceback
from pathlib import Path
from typing import Any

from . import config

# The last N calls, kept in memory. A ring buffer rather than a growing list so a
# long session cannot consume memory, and so the report shows what happened
# RECENTLY — which is what matters when someone says "it just broke".
_HISTORY: collections.deque = collections.deque(maxlen=60)
_FAILURES: collections.deque = collections.deque(maxlen=25)

_STARTED = datetime.datetime.now()

# Anything that could be a credential. Applied to every string on the way out.
# NOTE ON THE SEPARATOR. An earlier version of this matched an optional quote
# AFTER the colon but not before it, so the JSON form "refresh_token":"AQAB…"
# slipped straight through while the header form Authorization: Bearer … was
# caught. The test that found it is in the selftest and must stay there: a
# redaction regex that has never been shown to fire on a REAL credential shape is
# not a redaction regex.
_SECRET_KEYS = r"access[-_]?token|refresh[-_]?token|id[-_]?token|authorization|auth[-_]?token|client[-_]?secret|api[-_]?key|password|bearer"

_SECRET_PATTERNS = [
    # A JWT anywhere at all, regardless of what it is labelled.
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}(?:\.[A-Za-z0-9_\-]*)?"),
     "<JWT-REDACTED>"),
    # key : value, with quotes optional on BOTH sides of the separator.
    (re.compile(rf"(?i)([\"']?(?:{_SECRET_KEYS})[\"']?\s*[:=]\s*)[\"']?[A-Za-z0-9._\-/+]{{12,}}[\"']?"),
     r"\1<REDACTED>"),
    # Authorization header form, with or without a scheme.
    (re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._\-/+=]{12,}"), r"\1 <REDACTED>"),
]

# Argument names whose VALUES are commercial detail rather than diagnostic shape.
_CONTENT_KEYS = {
    "name_contains", "vendor_contains", "supplier_contains", "query",
    "code_or_name", "code_or_id", "number_or_id", "match",
}


# A key whose VALUE is a credential, however that value is shaped.
_SECRET_KEY_RE = re.compile(rf"(?i)^[\"']?(?:{_SECRET_KEYS})[\"']?$")


def redact(value: Any) -> Any:
    """Scrub anything token-shaped from any structure, recursively.

    Two distinct cases, and the second is easy to miss:

      "refresh_token=AQAB…"          the credential is INSIDE a string, so the
                                     patterns above match it
      {"refresh_token": "AQAB…"}     the credential is a dict VALUE and its label
                                     is the KEY — the value on its own is just an
                                     opaque string with nothing to match against

    The second case defeated an earlier version of this entirely, and it is the
    shape an error body or a captured header most often takes. So keys are checked
    as well as contents.
    """
    if isinstance(value, str):
        out = value
        for pattern, replacement in _SECRET_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, dict):
        scrubbed = {}
        for key, item in value.items():
            if isinstance(key, str) and _SECRET_KEY_RE.match(key.strip()):
                scrubbed[key] = "<REDACTED>"
            else:
                scrubbed[key] = redact(item)
        return scrubbed
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def _safe_args(arguments: dict[str, Any], include_content: bool) -> dict[str, Any]:
    """Keep the shape of the call; drop the commercial content unless asked."""
    out: dict[str, Any] = {}
    for key, value in (arguments or {}).items():
        if not include_content and key in _CONTENT_KEYS and isinstance(value, str):
            out[key] = f"<{len(value)} chars redacted>"
        elif isinstance(value, str) and len(value) > 120:
            out[key] = value[:120] + f"… (+{len(value) - 120})"
        else:
            out[key] = value
    return redact(out)


def record_call(tool: str, arguments: dict[str, Any], ms: int, ok: bool,
                note: str | None = None) -> None:
    _HISTORY.append(
        {
            "at": datetime.datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "args": arguments,
            "ms": ms,
            "ok": ok,
            **({"note": note} if note else {}),
        }
    )


def record_failure(tool: str, arguments: dict[str, Any], exc: BaseException | None = None,
                   detail: Any = None) -> None:
    entry: dict[str, Any] = {
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tool": tool,
        "args": arguments,
    }
    if exc is not None:
        entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["traceback"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-3000:]
    if detail is not None:
        entry["detail"] = detail
    _FAILURES.append(entry)


def _auth_state() -> dict[str, Any]:
    """Auth state WITHOUT the token. Never returns anything secret."""
    try:
        from . import auth

        state = auth.status()
        return {
            # needs_sign_in is the headline; signed_in must not be computed from
            # the 60-minute access token. See auth.status().
            "needs_sign_in": state.get("needs_sign_in"),
            "signed_in": state.get("authenticated"),
            "access_token_live": state.get("access_token_live"),
            "refresh_available": state.get("refresh_available"),
            "access_token_expires_in_minutes":
                state.get("access_token_expires_in_minutes"),
            "refresh_estimated_days_left": state.get("refresh_estimated_days_left"),
            "token_file_exists": Path(state.get("token_file", "")).exists(),
            "token_file": state.get("token_file"),
            "scope_recorded": state.get("scope_recorded"),
            "note": (
                "An expired ACCESS token is normal — it lasts 60 minutes and is "
                "renewed silently from a refresh token that lasts 15 days. Only "
                "needs_sign_in means a person must act."
            ),
        }
    except Exception as exc:  # noqa: BLE001 - a broken auth module is itself the finding
        return {"signed_in": "UNKNOWN", "auth_module_error": f"{type(exc).__name__}: {exc}"}


def _tool_state() -> dict[str, Any]:
    try:
        from . import registry

        return {
            "read_tools": registry.read_tools(),
            "write_tools": registry.write_tools(),
            "guarantee_problems": registry.assert_guarantee(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"registry_error": f"{type(exc).__name__}: {exc}"}


def collect(include_content: bool = False) -> dict[str, Any]:
    """Build the report. Never raises — a failure to diagnose is itself reported."""
    from . import __version__

    report: dict[str, Any] = {
        "report": "Forma MCP diagnostics",
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "share_with": "the person who maintains this plugin",
        "contains_no_credentials": True,
        "content_redacted": not include_content,
    }

    report["plugin"] = {
        "version": __version__,
        "location": str(Path(__file__).resolve().parent.parent),
        "session_started": _STARTED.isoformat(timespec="seconds"),
        "uptime_minutes": round((datetime.datetime.now() - _STARTED).total_seconds() / 60, 1),
    }

    report["environment"] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
    }

    try:
        report["configuration"] = {
            "api_base": config.API_BASE,
            "region": config.REGION,
            "hub": config.HUB_ID,
            "client_id_present": bool(config.CLIENT_ID),
            "client_id_tail": f"…{config.CLIENT_ID[-6:]}" if config.CLIENT_ID else None,
            "state_dir": str(config.STATE_DIR),
            "state_dir_exists": config.STATE_DIR.exists(),
            "write_allow_list": sorted(config.ALLOWED_CONTAINERS),
            "allow_all_containers": config.ALLOW_ALL_CONTAINERS,
            "env_overrides": sorted(k for k in os.environ if k.startswith("FORMA_")),
        }
    except Exception as exc:  # noqa: BLE001
        report["configuration"] = {"config_error": f"{type(exc).__name__}: {exc}"}

    report["auth"] = _auth_state()
    report["tools"] = _tool_state()

    report["recent_calls"] = [
        {**c, "args": _safe_args(c.get("args") or {}, include_content)} for c in _HISTORY
    ]
    report["failures"] = [
        {**f, "args": _safe_args(f.get("args") or {}, include_content)} for f in _FAILURES
    ]
    report["failure_count"] = len(_FAILURES)

    if not _FAILURES:
        report["note"] = (
            "No failures were recorded in this session. If the problem is that an "
            "ANSWER looked wrong rather than a call breaking, say what was asked, "
            "what came back, and what it should have said — that is not something "
            "this file can capture on its own."
        )

    # Redact the whole structure on the way out rather than trusting each call site.
    return redact(report)


def render(report: dict[str, Any]) -> str:
    """A readable text report. Plain text so it can be pasted anywhere."""
    lines: list[str] = []
    add = lines.append

    add("=" * 72)
    add("  FORMA MCP — DIAGNOSTIC REPORT")
    add("=" * 72)
    add(f"generated   {report.get('generated')}")
    add(f"plugin      v{(report.get('plugin') or {}).get('version')}")
    add(f"location    {(report.get('plugin') or {}).get('location')}")
    add("")
    add("This file contains NO tokens or credentials.")
    if report.get("content_redacted"):
        add("Search terms and record content have been redacted.")
    add("")

    def block(title: str, payload: Any) -> None:
        add("-" * 72)
        add(title)
        add("-" * 72)
        add(json.dumps(payload, indent=1, default=str))
        add("")

    block("ENVIRONMENT", report.get("environment"))
    block("CONFIGURATION", report.get("configuration"))
    block("AUTH  (no token included)", report.get("auth"))
    block("TOOLS", report.get("tools"))

    failures = report.get("failures") or []
    add("-" * 72)
    add(f"FAILURES  ({len(failures)})")
    add("-" * 72)
    if not failures:
        add("none recorded this session")
        if report.get("note"):
            add("")
            add(report["note"])
    else:
        for index, failure in enumerate(failures, 1):
            add(f"\n[{index}] {failure.get('at')}  tool={failure.get('tool')}")
            add(f"    args: {json.dumps(failure.get('args'), default=str)}")
            if failure.get("error"):
                add(f"    error: {failure['error']}")
            if failure.get("detail"):
                add(f"    detail: {json.dumps(failure['detail'], default=str)[:800]}")
            if failure.get("traceback"):
                add("    traceback:")
                for line in str(failure["traceback"]).splitlines()[-18:]:
                    add(f"      {line}")
    add("")

    calls = report.get("recent_calls") or []
    add("-" * 72)
    add(f"RECENT CALLS  ({len(calls)}, newest last)")
    add("-" * 72)
    for call in calls:
        flag = "ok " if call.get("ok") else "FAIL"
        add(f"  {call.get('at')}  {flag}  {str(call.get('tool')):<24} "
            f"{call.get('ms')}ms  {json.dumps(call.get('args'), default=str)[:90]}")
    add("")
    add("=" * 72)
    add("  END OF REPORT")
    add("=" * 72)
    return "\n".join(lines)


def write(include_content: bool = False, directory: Path | None = None) -> dict[str, Any]:
    """Write the report next to the token store, and return where it went."""
    report = collect(include_content)
    text = render(report)

    target_dir = directory or config.STATE_DIR
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        target_dir = Path.home()

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"forma-error-log-{stamp}.txt"
    path.write_text(text, encoding="utf-8")

    return {
        "written_to": str(path),
        "bytes": path.stat().st_size,
        "failures_captured": report.get("failure_count", 0),
        "calls_captured": len(report.get("recent_calls") or []),
        "contains_no_credentials": True,
        "content_redacted": not include_content,
    }
