# -*- coding: utf-8 -*-
"""Splice a payload into the Cost & Spend Desk shell, and check it first.

    python build_desk.py payload.json out.html [--shell shell.html] [--check]

The desk is one HTML file in two halves. The SHELL - the CSS, the markup and
about 500 lines of JavaScript - never changes between refreshes. The PAYLOAD is
one `<script id="payload" type="application/json">` block holding every figure
on the page. Nothing in the shell carries a date, a project name or a record,
so replacing the payload is the whole of a refresh.

That is the point of this script: the model writes payload.json (~30KB) and
this assembles the page (~85KB), instead of regenerating 1,000 lines of HTML
and silently dropping a chart or a link builder on the way.

It also refuses to build a payload that is wrong in the ways this page has
actually been got wrong:

  * a record pointing at a project key that is not in `projects`
  * a `docs` entry carrying a whole urn, or a url, instead of the bare id
    (the shell wraps the id itself - see references/desk-forma-reads.md)
  * an `age` far from `due` measured from `today`, which is what a refresh that
    updated the figures but not the arithmetic looks like
  * a `done` step that is not in that record's `chain`
  * the template's example rows left in

Warnings print and let the build through; errors stop it. Read the report
before publishing - it is the only look anyone gets at the page before it is
live, because the artifact cannot be rendered locally.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import os
import re
import sys

MARK_OPEN = '<script id="payload" type="application/json">'
MARK_SHUT = "</script>"
BLOCK = re.compile(
    re.escape(MARK_OPEN) + r"\s*(\{.*?\})\s*" + re.escape(MARK_SHUT), re.S
)

TITLE = re.compile(r"<title>(.*?)</title>", re.S)

SECTIONS = ("variations", "contracts", "invoices")
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)

# A record can sit at a state that is not one of its approval steps - it has
# come out the far end, or been pushed back to the start.
TERMINAL_STEPS = frozenset({
    "Ready to execute", "Sent back", "Sent back to draft", "Executed", "Closed",
})

# How far `age` may sit from `today - due` before it is worth a second look.
AGE_SLACK_DAYS = 3

errors = []
warns = []


def bad(msg):
    errors.append(msg)


def iffy(msg):
    warns.append(msg)


def parse_day(value):
    try:
        return dt.date(*[int(x) for x in str(value).split("-")])
    except Exception:
        return None


def check(payload):
    """Validate the payload. Returns a small dict of counts for the report."""
    if payload.get("example"):
        bad("payload still carries example:true - those are the template's "
            "placeholder rows, not Forma data")

    for key in ("me", "today", "projects"):
        if not payload.get(key):
            bad("missing top-level %r" % key)

    title = payload.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        bad("`title` is %r - it must be the page's name as text, or left out" % (title,))

    today = parse_day(payload.get("today"))
    if payload.get("today") and not today:
        bad("`today` is %r - it must be YYYY-MM-DD" % payload.get("today"))

    projects = payload.get("projects") or []
    keys = [p.get("key") for p in projects]
    for p in projects:
        for field in ("key", "name", "code", "c"):
            if not p.get(field):
                bad("project %r has no %r" % (p.get("code") or p.get("key"), field))
        if p.get("c") and not UUID.match(str(p["c"])):
            bad("project %s container %r is not a uuid" % (p.get("code"), p.get("c")))
    if len(set(keys)) != len(keys):
        bad("two projects share a `key`: %r" % (keys,))

    counts = {"projects": len(projects)}
    mine = 0

    for section in SECTIONS:
        rows = payload.get(section) or []
        counts[section] = len(rows)
        for row in rows:
            tag = "%s %s" % (
                section[:-1], row.get("num") or row.get("code") or row.get("id"))

            if row.get("p") not in keys:
                bad("%s points at project %r, which is not in `projects`"
                    % (tag, row.get("p")))
            if not row.get("id"):
                bad("%s has no `id` - the record link cannot be built without it" % tag)
            elif not UUID.match(str(row["id"])):
                iffy("%s `id` is not a uuid: %r" % (tag, row["id"]))

            amt = row.get("amt")
            if amt is not None and not isinstance(amt, (int, float)):
                bad("%s `amt` is %r - it must be a number, unquoted" % (tag, amt))

            chain = row.get("chain")
            if not isinstance(chain, list):
                bad("%s has no `chain` array (use [] when nothing is running)" % tag)
                chain = []
            done = row.get("done")
            if not isinstance(done, list):
                bad("%s has no `done` array (use [])" % tag)
                done = []
            for step in done:
                if step.get("s") not in chain:
                    iffy("%s signed-off step %r is not in its chain %r"
                         % (tag, step.get("s"), chain))
            if row.get("step") and chain and row["step"] not in chain \
                    and row["step"] not in TERMINAL_STEPS:
                iffy("%s current step %r is not in its chain %r"
                     % (tag, row["step"], chain))
            if row.get("with") and not row.get("step"):
                iffy("%s is with somebody but names no step" % tag)

            # `age` and `due` come from different places - `age` from Forma's own
            # overdue count on the approval step, `due` from the record - so they
            # disagree by a day or two quite legitimately. A week apart is the
            # thing worth catching: a refresh that took new figures and kept old
            # ages, which is how this page most easily starts lying.
            due = parse_day(row.get("due")) if row.get("due") else None
            if due and today:
                want = (today - due).days
                if row.get("age") is None:
                    iffy("%s has a due date but no `age` (Forma would say about %d)"
                         % (tag, want))
                elif abs(int(row["age"]) - want) > AGE_SLACK_DAYS:
                    iffy("%s `age` is %s but %s to %s is %d days - check the ages "
                         "were re-read, not carried over"
                         % (tag, row["age"], row["due"], payload["today"], want))
            if row.get("age") is not None and not row.get("due"):
                iffy("%s carries an `age` with no `due` to measure it from" % tag)

            for doc in row.get("docs") or []:
                urn = str(doc.get("u") or "")
                if not doc.get("n") or not urn:
                    bad("%s has a `docs` entry missing `n` or `u`" % tag)
                if urn.startswith("urn:") or "/" in urn or "?" in urn:
                    bad("%s doc %r carries a whole urn or url in `u` - store the "
                        "BARE id; the shell builds the link" % (tag, urn[:40]))
                elif urn and len(urn) > 40:
                    iffy("%s doc id is %d characters, longer than any seen so far"
                         % (tag, len(urn)))

            if row.get("with") and payload.get("me") \
                    and payload["me"] in str(row["with"]):
                mine += 1

            b = row.get("bud")
            if b:
                if not b.get("code"):
                    bad("%s `bud` has no `code`" % tag)
                for f in ("revised", "committed", "spent", "queued"):
                    if b.get(f) is not None and not isinstance(b[f], (int, float)):
                        bad("%s `bud.%s` is %r - must be a number" % (tag, f, b[f]))

    if not any(counts.get(s) for s in SECTIONS):
        bad("every section is empty - there is nothing to show")

    counts["with you"] = mine
    if payload.get("spendCounts"):
        iffy("`spendCounts` is not read by the shell - drop it rather than "
             "spending reads collecting it")
    return counts


def main():
    argv = sys.argv[1:]
    shell_path = None
    if "--shell" in argv:
        i = argv.index("--shell")
        shell_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    flags = set(a for a in argv if a.startswith("--"))
    args = [a for a in argv if not a.startswith("--")]

    if not args or (len(args) < 2 and "--check" not in flags):
        sys.exit("usage: build_desk.py payload.json out.html "
                 "[--shell shell.html] [--check]")

    payload_path = args[0]
    out_path = args[1] if len(args) > 1 else None
    if not shell_path:
        shell_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            os.pardir, "assets", "desk-template.html"))

    try:
        payload = json.loads(io.open(payload_path, encoding="utf-8").read())
    except ValueError as exc:
        sys.exit("payload.json will not parse: %s" % exc)

    counts = check(payload)

    print("PAYLOAD  %s" % os.path.basename(payload_path))
    for k, v in counts.items():
        print("  %-12s %s" % (k, v))
    print("  %-12s %s" % ("read", payload.get("today")))
    print("  %-12s %.1f KB" % ("size", len(json.dumps(payload)) / 1024.0))

    if warns:
        print("\nWARNINGS (%d) - the build goes ahead, read them anyway" % len(warns))
        for w in warns:
            print("  ? " + w)
    if errors:
        print("\nERRORS (%d) - nothing was written" % len(errors))
        for e in errors:
            print("  x " + e)
        return 1
    if "--check" in flags:
        print("\nOK  payload is sound (checked only, nothing written)")
        return 0

    shell = io.open(shell_path, encoding="utf-8").read()
    found = BLOCK.search(shell)
    if not found:
        sys.exit("no payload block found in %s - is that the desk shell?" % shell_path)

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # One record per line keeps a published diff readable and a hand-check possible.
    body = re.sub(r'(,)("(?:projects|variations|contracts|invoices)":)',
                  r"\1\n\2", body)
    body = body.replace('[{"', '[\n {"').replace('},{"', '},\n {"')

    page = BLOCK.sub(
        lambda _: MARK_OPEN + "\n" + body + "\n" + MARK_SHUT, shell, count=1)

    if re.search(r">Read \d+ \w+ \d{4}<", page):
        sys.exit("that shell has a date baked into its markup - use the packaged "
                 "template, whose masthead and footer read the payload")

    # The page's <title> is its name in the gallery and the browser tab. The
    # shell says "Cost & Spend Desk"; a desk its owner has renamed carries the
    # name in the payload's `title`, so a refresh never quietly renames it back.
    shell_title = TITLE.search(page)
    if payload.get("title"):
        name = html.escape(payload["title"].strip(), quote=False)
        page = TITLE.sub(lambda _: "<title>" + name + "</title>", page, count=1)
        print("  %-12s %s" % ("title", payload["title"].strip()))
    elif shell_title:
        print("  %-12s %s (the shell's - set `title` in the payload if the live page "
              "is called something else)" % ("title", html.unescape(shell_title.group(1))))

    io.open(out_path, "w", encoding="utf-8").write(page)
    print("\nOK  %s  %.1f KB  (shell %.1f KB + payload %.1f KB)"
          % (os.path.basename(out_path), len(page) / 1024.0,
             (len(shell) - len(found.group(1))) / 1024.0, len(body) / 1024.0))
    print("    publish with the Artifact tool, passing `url` to update in place")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
