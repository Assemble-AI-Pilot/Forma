#!/usr/bin/env python3
"""Sign in to Forma. Run this once, then again whenever the refresh token lapses.

    python3 login.py            sign in (opens a browser)
    python3 login.py status     show the stored credential without signing in
    python3 login.py refresh    renew the access token
    python3 login.py logout     delete the stored tokens
    python3 login.py diagnose   write a shareable error report
    python  login.py setup      point .mcp.json at THIS interpreter (run once,
                                and on Windows in particular)

Deliberately computes its own location rather than assuming one. An earlier
Aconex build hard-coded the sign-in path, passed every test, and was wrong for
every recipient — the bug was invisible until the project was moved. This works
wherever the plugin is unzipped.

Tokens are stored in ~/.forma-mcp/, outside the plugin folder, so upgrading is
genuinely "replace the folder" and a zipped plugin never carries a credential.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forma_mcp import auth, config  # noqa: E402


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "login"

    if command == "setup":
        # THE WINDOWS FIX. A shipped .mcp.json has to name an interpreter, and no
        # single name works everywhere: `python3` does not exist on a standard
        # python.org Windows install, and `python` often does not exist on macOS.
        # Whichever we ship is wrong for somebody, and the failure is opaque — the
        # MCP server simply never starts and the tools are silently absent.
        #
        # So setup writes the ABSOLUTE path of the interpreter that is running it.
        # After this there is no PATH dependency left to get wrong.
        import json as _json
        import platform as _platform

        root = Path(__file__).resolve().parent
        mcp = root / ".mcp.json"
        print("Forma MCP setup\n" + "=" * 60)
        print(f"  python      {sys.version.split()[0]}")
        print(f"  interpreter {sys.executable}")
        print(f"  platform    {_platform.platform()}")
        print(f"  plugin      {root}")

        if not mcp.is_file():
            print(f"\n  PROBLEM: {mcp} is missing. Re-install the plugin.")
            return 1

        data = _json.loads(mcp.read_text(encoding="utf-8"))
        changed = []
        for name, server in (data.get("mcpServers") or {}).items():
            before = server.get("command")
            if before != sys.executable:
                server["command"] = sys.executable
                changed.append(f"{name}: {before} -> {sys.executable}")
        if changed:
            mcp.write_text(_json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print("\n  .mcp.json updated:")
            for line in changed:
                print(f"    {line}")
        else:
            print("\n  .mcp.json already points at this interpreter.")

        print("\n  checking the server starts…")
        import subprocess
        module = next(iter((data.get("mcpServers") or {}).values()), {}).get(
            "args", ["-m", "forma_full.server"])[-1]
        proc = subprocess.run(
            [sys.executable, "-B", "-m", module, "--selftest"],
            cwd=root, capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"},
            timeout=180,
        )
        passed = proc.stdout.count("PASS")
        if proc.returncode == 0:
            print(f"    OK — {passed} self-checks passed")
        else:
            print(f"    FAILED ({passed} passed). Output:\n")
            print("\n".join(proc.stdout.splitlines()[-25:]))
            print("\nRun:  python login.py diagnose   and send the file on.")
            return 1

        state = auth.status()
        print("\n  signed in   " + ("yes" if state.get("authenticated")
                                     else "NO — run:  python login.py"))
        if state.get("authenticated"):
            print(f"  token file  {state['token_file']}")
            print(f"  protection  {state.get('file_protection')}")
            who = auth.whoami()
            if not who.get("error"):
                print(f"  account     {who.get('name')} <{who.get('email')}>")

        print("\n" + "=" * 60)
        print("  Setup complete. Restart Claude Code to pick up the change.")
        return 0

    if command == "diagnose":
        # Deliberately importable even when much of the plugin is broken: the case
        # worth reporting is usually the case where the tool itself will not run.
        from forma_mcp import diagnostics

        result = diagnostics.write(include_content="--include-content" in sys.argv)
        print("Diagnostic report written.\n")
        print(f"  {result['written_to']}")
        print(f"  {result['bytes']:,} bytes, {result['failures_captured']} failure(s) captured")
        print("\nThis file contains no tokens or credentials.")
        print("Send it to whoever maintains this plugin.")
        return 0

    if command == "status":
        state = auth.status()
        print(f"token file : {state['token_file']}")
        if not state["authenticated"]:
            print(f"signed in  : NO ({state.get('reason', 'token expired')})")
            print("\nRun: python3 login.py")
            return 1
        print(f"signed in  : yes, {state['access_token_expires_in_minutes']} minutes remaining")
        who = auth.whoami()
        if who.get("error"):
            print(f"account    : could not confirm ({who['error']})")
        else:
            print(f"account    : {who.get('name')}  <{who.get('email')}>")
        print(f"refreshable: {'yes' if state['refresh_available'] else 'NO'}")
        print(f"scope       : {state['scope_recorded'] or 'not recorded'}")
        print(f"             ({state['scope_note']})")
        return 0

    if command == "refresh":
        auth.refresh()
        print("Refreshed.")
        return 0

    if command == "logout":
        result = auth.logout()
        print("Removed." if result["removed"] else "Nothing stored.")
        return 0

    if command != "login":
        print(f"Unknown command: {command}", file=sys.stderr)
        return 2

    print("Signing in to Autodesk. A browser window will open.")
    print(f"Requesting: {config.SCOPES}\n")
    try:
        auth.login()
    except auth.AuthError as exc:
        print(f"\nSign-in failed: {exc}", file=sys.stderr)
        return 1

    state = auth.status()
    who = auth.whoami()
    print("\n" + "=" * 68)
    if who.get("error"):
        print(f"  Signed in, but could not confirm the account ({who['error']}).")
    else:
        print(f"  Signed in as:  {who.get('name')}   <{who.get('email')}>")
        print("")
        print("  ^ CHECK THIS IS YOU, and that it is your Assemble account.")
        print("    Everything this plugin does is attributed to that person and")
        print("    limited to their Forma permissions. Signing in with the wrong")
        print("    account works perfectly — against the wrong access.")
        print("    Wrong account?  python login.py logout   then sign in again.")
    print("=" * 68)
    print(f"\nAccess token valid for {state['access_token_expires_in_minutes']} minutes.")
    print(f"Tokens stored at {state['token_file']}")
    print(f"File protection: {state.get('file_protection')}")
    if not state["refresh_available"]:
        print("\nWARNING: no refresh token was issued. Check offline_access is in the scopes.")
    print("\nWrites are confined to: " + (
        "ALL PROJECTS" if config.ALLOW_ALL_CONTAINERS
        else ", ".join(config.KNOWN_CONTAINERS.get(c, c) for c in sorted(config.ALLOWED_CONTAINERS))
        or "none"
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
