# forma-user 0.11.0 — the universal plugin

Working plan, 6 Oct 2026. Sources: `Superagent/forma-user-changes.md` (agreed 5–6 Oct in the
superagent design session) and Jarvis's direction of 6 Oct. Not shipped in the plugin.

## The direction

- **Universal.** One plugin any Assemble person installs, from a private Assemble GitHub repo.
  Nothing in it is specific to one person.
- **The superagent decides; forma-user does the Forma work.** forma-user keeps the connector, the
  guards, the front doors and step skills, the approval documents, the forma-user skill and
  desk-bot's reads.
- **Out of forma-user:** the **morning routine** and **forma-reporting**. Both are built per
  person, with their own dashboards, in the superagent. (The superagent's sweep already
  refreshes the cost desk each weekday morning.)

## 1. Remove

| What | Where |
|---|---|
| The morning routine | scout-bot's "The morning routine" section; desk-bot's "offer to keep it current" and scheduled-task advice; the skill tree's routine box; README, INSTALL, CHANGELOG. The payload's `refresh` stays optional, set only by whoever really schedules a refresh |
| forma-reporting | router, README, skill tree, plugin.json description |
| Team mode (change 1) | desk-template.html's team branches, desk-bot's "Two kinds of desk", payload `team`, desk-payload.md. Keep the owner-only `suggestions`/`nextsteps`/`scoutrun` rules. Keep the `user` capability only if Next steps still needs `me()` (it can use `isOwner()`, which needs no declaration) |
| Anything tied to Jarvis | desk-bot's record of the retired desk (`SQAthoLvNFHk5AWTbQVgem`) and "Project Dashboard" naming; scout-bot's "Jarvis Mellor's is Project Dashboard"; the CRC template's hard-coded **Prepared by: Jarvis Mellor** and the **Jarvis Mellor — Senior Development Manager (Project Lead)** signature row; the fill script's "Jarvis is always Yes"; var-bot examples |
| The router copy step | Plugin skills are now listed and invoked automatically, and a skill outside `skills/` is not loaded from a marketplace install. Either move `forma-bots` into `skills/` (installs itself) or retire it. INSTALL section 8 goes either way |

## 2. Change (forma-user-changes.md)

- **Universal approval documents.** CRC template and fill script take `prepared_by`,
  `project_lead_name`, `project_lead_position`; the project lead signs "always Yes". The approver
  bands (Sam Delmenico over 25,000, Carolyn Viney over 1,000,000) move into one reference file,
  so a change of people is one edit. Same for var-bot's preparer.
- **Work orders (change 2).** `references/work-order.md`: the shape the superagent hands over
  (project, family, record, from/to, figures, evidence, owner's decision and comment — the
  `suggestions`/`nextsteps` shape). contract-bot and var-bot accept one.
- **The menu of moves (change 3).** `references/moves.md`: for each move, from/to, step skill,
  front door, inputs, what the read-back must show. scout-bot keeps only the signal side.
- **scout-bot frozen (change 4).** Works as is, no email reading, marked "moving to the
  superagent"; if it runs, it writes to the person's dashboard db, not an old desk (change 9).
- **Writes need the owner in a conversation (change 6).** Stated in both front doors: a Proceed on
  any dashboard never replaces the chat confirmation or `confirm_write`.
- **desk-bot's dashboard target (change 9).** When the person's desk lives on their superagent
  dashboard, a refresh reads `cost/desk`, runs the Forma reads and `build_desk.py --check`, writes
  the payload back (pinned `set`), publishes nothing, and clears `costdecisions` for records no
  longer read. A standalone desk keeps working, and republishes only when something changed.
  Template and payload changes are made together with the dashboard's copy.

## 3. Add

- **Forma Docs read tools (change 7), read-only:** discipline folders → dated issue folders →
  files; changed-since a date; first pages, name, uploader, date and a link. Built against
  Clayton's Design Management structure.
- **A record's attachments, read-only:** the superagent's 6 Oct refresh found new records with no
  document links because forma-user cannot list a record's attachments on their own.
- **A release check** (`tools/release_check.py`): what the GitHub build already enforces — no
  sensitive workbook columns, skill frontmatter valid, no dollar-digit in skills, no credentials,
  the selftest — runnable by whoever cuts a release.

## 4. GitHub

- **Layout:** a plugin marketplace. `.claude-plugin/marketplace.json` at the root,
  `plugins/forma-user/` beneath it, so Aconex or admin plugins can join later. **Private**, in
  Assemble's org.
- **Installing:** the desktop app has no button for GitHub marketplaces, so each release attaches
  the `.plugin` file (download, then the app's plugin manager). Terminal users:
  `claude plugin marketplace add <org>/<repo>` with git signed in.
- **The working copy moves out of OneDrive.** ThreatLocker blocks shell and Python writes there.
  Clone the repo to a local folder (GitHub Desktop, or Git for Windows — IT may need to allow it).
- **Never committed:** the master Entity Bible (only the extract), backups, scratch files, pages
  with real figures, sign-in tokens. The `.gitignore` covers these.

## 5. Docs and version

plugin.json description, README, INSTALL (install from a release; no router copy), the skill tree
(forma-user as the Forma hands; desk-bot stays; scout-bot moving; no routine, no reporting),
CHANGELOG. Version **0.11.0-beta**.

## Done on 6 Oct

- **Tax file numbers removed.** The plugin's Entity Bible becomes an extract of the seven columns
  `lookup.py` reads, made by `scripts/make_entity_extract.py`. Checked: none of the master's 63
  TFNs or 43 ASIC corporate keys appear anywhere in it, and lookups give identical answers.
- `lookup.py entity --list` and `costcode --list` fixed (they failed before).
- The GitHub upload is built and checked (0.10.0-beta content, TFN-free).

## Still open, unchanged

- Phase B: contract steps 2 and 3, coached on a live Clayton contract.
- The stage 3 compliance document: a decision, then a sandbox browser test.
- forma-admin carries an older `forma_mcp`; it joins the repo later as its own plugin.
- Docs write tools (filing consultant documents): undecided, not built.
