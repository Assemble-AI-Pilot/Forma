---
name: desk-bot
description: Builds and refreshes Assemble's Cost & Spend Desk — the published page showing every contract, variation and invoice that has stopped moving, who is holding it, how long it has been there, and the budget line it draws on. Use it to refresh the desk with current Forma figures, to add or drop a project, or to stand a desk up for a different project set. Also use it when someone asks why the desk is stale, what the page can and cannot do, or asks for "the desk", "the dashboard", "the portal", "the approvals desk", "the invoice desk" or "the cost desk".
---

# desk-bot — the Cost & Spend Desk

One published page, three supertabs. **Cost** carries contracts and variations;
**Spend** carries invoices. Under each sits a Summary and one sub-tab per
project. Every record shows its approval chain, who is holding it, how many days
it is overdue, the budget line it draws on, and a link to each of its
attachments. **Next steps**, visible only to the desk's owner, carries
scout-bot's suggested moves (see the end of this file).

desk-bot sits across the whole **Cost admin** group — contracts, variations
and expenses — as the viewer. It reads; it never moves anything.

**A desk belongs to whoever published it.** There is no shared, central desk and
this skill must not assume one. Before refreshing anything, find the caller's
own: Artifact `list` with `scope: "mine"` and look for the title **Cost & Spend
Desk** (or the name its owner gave it — Jarvis Mellor's is **Project Dashboard**).

- **Found one** — refresh that URL, in place.
- **Found none** — they have never built one. Say so, and offer to: it is the
  same steps, publishing **without** `url` so it gets its own link. Then record
  that link for them.
- **They name a URL they do not own** — a publish to it is refused, and dropping
  `url` to get past the refusal silently creates a second desk with a different
  link. Do neither. Explain that the owner has to refresh their own copy, and
  offer to build the caller theirs.

Jarvis Mellor's desk — Footscray Whitehall (WSF0017) and Clayton Carinish Road
(CRC0209) — is at <https://claude.ai/artifact/SQAthoLvNFHk5AWTbQVgem>. It is
recorded here so it is recognisable, **not** as a default to publish to.

## The one thing to understand before touching it

The page is **one HTML file in two halves**:

| | |
|---|---|
| **The shell** | ~75KB of CSS, markup and JavaScript. Holds no date, no project name and no record. Lives in `assets/desk-template.html`. |
| **The payload** | One `<script id="payload" type="application/json">` block, ~35KB, holding every figure on the page. |

A refresh replaces **the payload and nothing else**. The masthead stamp, the
footer's read date, the project list and both ledes all render from it, so there
is nowhere for a stale date to hide and nothing to remember to edit twice.

So do not regenerate the page. Write `payload.json` and run the builder:

```bash
python scripts/build_desk.py payload.json desk.html
```

It validates first and refuses a payload that is wrong in the ways this page has
actually been got wrong — a record pointing at a project that is not in the
list, a document urn stored where a bare id belongs, ages carried over from an
older read. Read its report.

## You can see the page before you publish it — do

This was believed impossible for the whole first build, and it is not. The
Browser pane cannot open a local **file**, but a local **server** is not a file:

```bash
# .claude/launch.json
{"version":"0.0.1","configurations":[{"name":"desk-preview",
 "runtimeExecutable":"python","runtimeArgs":["-m","http.server","8099",
 "--directory","<folder holding the html>"],"port":8099}]}
```

`preview_start` that config, navigate to
`http://localhost:8099/<file>.html`, then `read_console_messages` and
`get_page_text`. Every render path runs for real. `javascript_tool` will read
state out of the live page, which is how team mode's four branches were checked.

Two things behave differently there, and neither is a bug to fix:

- **`python -m http.server` sends no charset**, so text arrives as mojibake
  (`Â·`, `âˆ'`). The artifact skeleton supplies one. Add
  `<meta charset="utf-8">` to a preview copy if it bothers you; never to the
  page you publish.
- **`window.claude` does not exist**, so `db` and `user` resolve to null. That
  is the right way to test that the page still works without them — and on a
  team desk it is exactly the fail-closed path. The Next steps tab stays hidden
  for the same reason.

The script runs straight out of the plugin directory — no staging needed, unlike
var-bot's, because `~/.claude/plugins/` is not under `%APPDATA%\Roaming`.

## Rules that are not preferences

**Read only.** Every call this skill makes is a read. **Never pass
`confirm_write`.** The desk shows decisions; it does not take them.

**The page has no route to Forma.** A published artifact can reach claude.ai
connectors, not a local MCP plugin, so approving on the page cannot commit
anything. Decisions **queue** in the artifact's `db` and are executed later
through `forma_review`, one record at a time, by a person. The footer says so and
that footer stays.

**Links, never documents.** A record carries a file **name and a bare id** — two
short strings per attachment. Never fetch, embed or base64 a document into this
page. The shell builds the Docs link itself.

**Project every read.** Pass `fields` on every raw request. An unprojected
Footscray list runs to hundreds of thousands of tokens; the whole refresh should
cost a few thousand. `references/desk-forma-reads.md` has the recipe and the
figures.

**Never invent a figure to fill a field.** Every field is optional except the
handful the builder insists on. A missing budget line renders as "—"; a made-up
one reads as fact.

**Publish by `url`.** Pass the artifact's `url`, and omit `favicon` and `icon`
so it keeps them. A publish without `url` creates a second desk with a different
link. Omit `capabilities` too on an ordinary refresh, which carries the stored
declaration forward. Any publish that **does** declare them (turning team mode
on, or a first desk) must declare the whole set, owner-only scout rules
included, because a declaration replaces what is stored:

```json
{"db": {"rules": [
   {"path": "suggestions", "read": "owner", "write": "owner"},
   {"path": "nextsteps",   "read": "owner", "write": "owner"},
   {"path": "scoutrun",    "read": "owner", "write": "owner"}]},
 "user": {"scopes": ["profile"]}}
```

Dropping those rules would show suggestions drawn from the owner's mailbox to
everyone the desk is shared with. The profile scope is what supplies viewer
names; without it a team desk cannot identify anyone and every row goes
unclaimed.

**Keep the page's own name.** The shell is titled `Cost & Spend Desk`. A desk
its owner has renamed carries the name in the payload's `title`, and the builder
writes it into the page's `<title>` on every build. The first time you refresh a
renamed desk, take `title` from the live page's `<title>`; after that it rides
along in the payload. Leave it out and a renamed desk quietly reverts.

## Refreshing the desk

1. **Read the current payload** — Artifact `read` on **the caller's own** desk
   URL, then take the `<script id="payload">` block. You need it for the ids, the
   `chain` shapes and the document ids you would otherwise re-read. Note the
   page's `<title>` too.
2. **Re-read Forma** — the sequence in `references/desk-forma-reads.md`.
3. **Write `payload.json`** — schema in `references/desk-payload.md`. Set
   `today` to the run date, and carry `team` and `title` through unchanged. On a
   personal desk `me` drives the "With you" count and the highlighted rows, so
   keep it accurate; on a team desk each viewer supplies their own and `me` is
   only a record of who built it.
4. **Build** — `python scripts/build_desk.py payload.json desk.html`, and read
   the report, including the `title` line.
5. **Publish** — Artifact `publish` with `file_path` and `url`.
6. **Say what moved** — what cleared since the last read, what is new, what
   crossed 90 days. A refresh that only says "done" wastes the read.

## Somebody's first desk

Most runs of this skill will be for a person who has never had a desk, on
projects this file has never heard of. Establish two things before reading
anything else, because both are silent when wrong.

**1. Which projects — ask, do not assume.** `forma_projects` returns
`project`, `job_number` and `container_id`, which drop straight into
`projects[]` as `name`, `code` and `c`. But it lists everything that person can
*see*, and access is not involvement: most people can see far more projects than
they work on. Ask which ones belong on their desk. Two to four is a desk; twenty
is a list nobody opens.

If it comes back **empty, that is not an answer** — it almost always means the
Autodesk app has not been provisioned against the hub for them, which looks
exactly like having no projects. The tool says so in its own reply. Pass that on
rather than telling somebody they have no access.

**2. Who they are, as Forma spells it.** `me` is matched against the `with`
strings, which come from Forma, so a desk built with the wrong spelling shows a
correct page on which **nothing is theirs** — no highlighted rows, no actions,
and no error. Take the spelling from how they actually appear in an approval step
(`forma_approval_status` returns assignee names), and if you have to ask, confirm
it against a real record before building on it. On a **team** desk this matters
less: each viewer supplies their own name and `me` is only a record of who built
the desk.

Then the ordinary steps, with three differences: start from
`assets/desk-template.html` rather than a read of the live page; put those
projects in `projects`; and publish **without** `url` so it gets its own
artifact — then record that link, because from then on it is refreshed in place
like any other desk.

The template renders on its own with clearly-marked example rows. The builder
refuses to publish a payload still carrying `"example": true`, so placeholder
data cannot reach a real desk.

Then **offer to keep it current**, because a desk nobody refreshes is worse than
no desk: it is a stale page that looks live. Create a scheduled task that
invokes this skill — weekday mornings suits a desk people check before standing
up — and put its name and time in the payload's `refresh`, which is what the
footer tells the reader. Leave `refresh` out and that note stays hidden: better
an absent promise than a false one. The cost team's **morning routine** does
this and then runs scout-bot; see scout-bot's skill.

A scheduled task is per-machine and per-person. Yours does not refresh anybody
else's desk, and theirs does not refresh yours.

## Two kinds of desk

| | `team` | `me` | Who sees what |
|---|---|---|---|
| **Personal** | omitted | the person it was built for | Private to them. Built from their own Forma login, so it holds only what their ACC account can see. |
| **Team** | `true` | ignored for "mine" | Shared with colleagues. Holds everything for its projects, and marks each viewer's own rows. |

**A team desk scopes nothing.** It cannot: the figures are baked into the page,
and the page has no route to Forma to re-read them per viewer. Everyone with the
link sees every record on it, and the payload is readable in the page source. It
marks what is *relevant* to each viewer; it does not hide the rest. The page says
so on itself, in team mode, and that notice is not to be removed - a shared desk
that looked private would be the one genuinely dangerous version of this page.

**So when someone wants "only what's relevant to my account", build them a
personal desk** — their own Forma login is what does the filtering, and it is
Autodesk's own permissions rather than anything written here.

**Team mode fails closed.** `me` is only trusted on a personal desk. On a team
desk the viewer's name comes from the `user` capability, and if that cannot
resolve - a public link, a viewer outside the organisation, the capability
refused - then nothing is marked as theirs and no decision can be queued. The
failure worth designing against is offering one person somebody else's
approvals.

Team mode needs the `db` and `user` declaration under "Publish by `url`" above,
with the owner-only scout rules; the profile scope is what supplies names. Queued
decisions then carry who queued them, which is most of the point of a shared desk.

## When someone else runs this

Nothing here is shared by default, and three separate identities are in play.

**The Forma reads are theirs.** Each person signs in with their own Autodesk
account (`login.py`, tokens in `~/.forma-mcp/`), so a desk shows what that person
can see in ACC. Two people on different projects get different desks from the
same skill, and someone without access to a project simply gets nothing for it
rather than an error worth chasing.

**The page is theirs.** A published artifact lands in the publisher's own
claude.ai account and is **private until they share it**. A desk shared from the
page's share menu can be read by colleagues but **updated only by its owner** —
which is why this skill looks up the caller's own desk rather than carrying one
URL for everybody.

**The queued decisions are not private.** The page writes them to a shared `db`
path (`decisions/<record id>`), so on a *shared* desk every signed-in viewer in
the organisation sees what has been queued, and those who can interact can queue
their own. On an unshared desk it makes no difference. Worth saying out loud
before anyone shares a desk, because a queued send-back carries a typed comment
with it.

## The Next steps tab — scout-bot's suggested moves

A third supertab beside Cost and Spend. It is **not** in the payload:
scout-bot (`forma-user:scout-bot`) reads the owner's work email and Aconex, and
writes each suggested move straight into the artifact's `db`. A desk refresh
never touches it, and it never touches the payload.

| Path | Written by | Holds |
|---|---|---|
| `suggestions/<id>` | scout-bot, through `ArtifactData` | one suggested move, its evidence, and any later update |
| `nextsteps/<same id>` | the owner, on the page; Claude adds `result` | Proceed or Hold, a comment, then the outcome |
| `scoutrun/latest` | scout-bot | when it last ran and what it could and could not read |

All three are **owner-only by db rule**, because the evidence comes from a
personal mailbox. The page hides the tab from anyone else. This was checked on
3 Oct 2026: a row the owner can read lists as empty at `as_level: "admin"`.

The owner works down the list and marks each suggestion **Proceed** (with an
optional comment for Claude) or **Hold** (with a comment saying what to wait
for). The page records the call and nothing else. When the owner says "process
my next steps", Claude carries out the Proceeding ones, confirming each Forma
write in chat as the step skill requires. The scout reads the hold comments on
its next run and brings a held card back when it sees what was being waited for.
`references/scout-suggestions.md` has the format, the processing steps and the
hold rules.

## What the desk deliberately does not do

- **It does not approve anything.** See above.
- **It does not show every record** — only what has stopped moving. A record in
  a healthy queue is noise on a desk about things that are stuck.
- **It does not carry OCO or RCO variations.** Those are the investor side.
- **It does not re-derive Forma's own arithmetic.** `age` is Forma's overdue
  count, not a subtraction the page performs.

## If a figure on the desk is questioned

Read it back from Forma and quote both. The desk is a snapshot with a date on
it, and a number that was right at 07:02 can be wrong by lunchtime. Never defend
a figure from the payload alone — the payload is what the page says, not what
Forma says.

## Files

| | |
|---|---|
| `assets/desk-template.html` | The shell, with example rows. Cut from the live page, so it never drifts from what is published. |
| `scripts/build_desk.py` | Validates a payload, splices it in and writes the page's `title`. `--check` validates without writing. |
| `references/desk-payload.md` | Every field the shell reads, and what it does with it. |
| `references/desk-forma-reads.md` | Which calls to make, in order, and the token discipline that keeps a refresh cheap. |
| `references/scout-suggestions.md` | The `db` format scout-bot writes for the Next steps tab. |
