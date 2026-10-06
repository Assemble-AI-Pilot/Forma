# Changelog

## 0.10.1-beta — 6 Oct 2026

The first version prepared for Assemble's GitHub repository.

- **The Entity Bible is now an extract.** The plugin carries only the seven columns `lookup.py`
  reads — entity name, group, purpose, project address, ACN, ABN, registered address. The master's
  tax file numbers, ASIC corporate keys, officeholders, shareholders, insurance details and
  comments are gone. `scripts/make_entity_extract.py` regenerates the extract from the master
  whenever finance updates it; the master itself is never committed. Lookups give identical
  answers from the extract and the master.
- `lookup.py entity --list` and `costcode --list` work (argparse read `--list` as an option, so
  both failed with "term required").
- Releases are built for a plugin-marketplace repository (`plugins/forma-user/`) with a release
  `.plugin` file, and checked for sensitive workbook columns, credentials and skill-file problems
  before they are written.

## 0.10.0-beta — 3 Oct 2026

The plugin's architecture now follows Assemble's cost-admin workflow. Phase A of the 0.10.0 plan;
Phase B builds contract steps 2 and 3 on a live Clayton contract and ends with the full 0.10.0.

### Structure

- **Two groups.** *Cost admin* — contract-bot, var-bot, desk-bot, scout-bot (expense-bot to come).
  *Forma information* — forma-user (forma-reporting to come). `docs/skill-tree.svg` draws it.
- **Front doors over step skills.** contract-bot routes on the contract's Forma status to
  `contract-vendor-selection`, `contract-vendor-approval` and `contract-vendor-execution`. var-bot
  routes on the evidence to `variation-estimated`, `variation-proposed` and `variation-committed`.
  Each front door keeps the files and rules its steps share.
- **Router** (`router/forma-bots`) regrouped to match, front doors only, with routes for "run the
  scout" and "process my next steps". gem-bot is retired; contract-bot supersedes it.

### Contracts

- `contract-vendor-selection` is the previous contract-bot (CRC Recommendation, then the draft
  contract), plus the **Agreement type** field: one of the three default agreements or a bespoke
  one, mapped to Forma's Agreement Type attribute.
- `contract-vendor-approval` and `contract-vendor-execution` are outlines of the agreed process,
  saying exactly what works today. Built in Phase B.
- `skills/contract-bot/references/contract-lifecycle.svg` — the agreed three-step workflow, with
  what is built and what a person does.
- Checked against Clayton and Footscray history: Executed is set by a person (28 of 32 contracts,
  seconds after approval); approval lands as Sent; every contract matches an approval workflow.

### Variations

- var-bot split into its three stages. The tested instructions moved unchanged; the one stated
  change ("may press Send") now matches the code, which refuses it.
- `variation-lifecycle.svg` fixed: one shared Scope Item (not one per record), the missing `sent`
  step, the SCO's draft-only bot step, and the built / to-build key.
- The stage 3 **compliance document** is researched, not built: the API cannot attach to a
  compliance requirement, and only the Approved Variation can carry one. `forma-mechanics.md` §5b.

### Desk and scout

- desk-bot: the **Next steps** tab, owner-only by db rule; the page keeps a renamed title through
  the payload's `title`; the Next steps eyebrow says *Cost Admin*.
- **scout-bot** (new): reads Aconex — and email once connected — for evidence that a contract or
  variation can move, and writes suggested moves to the owner's desk. Never writes to Forma.
  Carries out "process my next steps" through the front doors, every write confirmed in chat.

### Server (`forma_mcp`)

- **Workflow rules.** The hard-coded allow-list is now `client.WORKFLOW_RULES`: each row names the
  move, the owning step skill, its preconditions and where it was measured. This release ships the
  same four variation steps, so behaviour is unchanged. 35 new selftest checks.
- The selftest's write-surface check was stale (it predated the four `forma_raise_*` tools) and had
  failed on every release since; fixed.
- `plugin_version` in diagnostics now reports the real version (it said 0.7.0 since 0.7.0).

### Documents and docs

- `fill_recommendation.py`: unfilled cells are now blank, not yellow prompts (as documented); lists
  every blank cell; `"nil"` writes the standard nil forecast; reads a JSON file with a Windows BOM.
- README rewritten: project confinement is **off** by default (`FORMA_ALLOWED_CONTAINERS="*"`), the
  Beta-corrections link points at forma-admin, the version is current. INSTALL updated.
- No `SKILL.md` contains a dollar sign followed by a digit any more — Claude Code substitutes `$0`,
  `$1`, … with the user's words, which had turned thresholds into nonsense.

### Known gaps

- Contract steps 2 and 3, and setting Pending Vendor Input (Phase B).
- The stage 3 compliance document (needs a decision, then a browser test on the sandbox).
- The morning routine is described but not yet scheduled.
- forma-admin carries an older copy of `forma_mcp` (no variation rules, no schedule-change fix).
