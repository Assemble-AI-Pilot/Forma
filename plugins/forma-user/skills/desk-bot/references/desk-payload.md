# The desk payload, field by field

Every figure on the page comes from here. Nothing in the shell carries a date, a
project name or a record, so this file is the whole of what a refresh writes.

Numbers are **unquoted JSON numbers**, AUD excluding GST. A negative amount is a
credit back to the project and the page renders it as such. Dates are
`YYYY-MM-DD`. **Every field below is optional unless marked required** — a
missing one renders as "—" or drops its block; an invented one reads as fact.

## Top level

| Field | | |
|---|---|---|
| `me` | **required** | The signed-in person's full name, as Forma spells it. Drives the "With you" tile and the highlighted rows: a record is yours when `with` contains this string. |
| `today` | **required** | The run date. Becomes "Read 18 Sep 2026" in the masthead and the footer's read date. |
| `projects` | **required** | See below. Generates the sub-tabs, the project codes, the deep links and the ledes' project phrase. |
| `refresh` | | `{"task": "...", "when": "weekdays at 7:02am"}` — the scheduled task keeping this desk current. Omit it and the footer's refresh note stays hidden. |
| `variations` `contracts` `invoices` | | The records. At least one must be non-empty. |
| `team` | | `true` makes this a **team desk**: the page identifies each viewer and marks their own rows, instead of trusting `me`. Set it on a desk that will be shared; leave it out for a personal one. See the skill. |
| `title` | | The page's name, when its owner has renamed it — `"Project Dashboard"`. The builder writes it into `<title>`, which is the name in the gallery and the browser tab. Omit it and the page keeps the shell's `Cost & Spend Desk`. Carry it forward on every refresh, like `team`. |
| `example` | | `true` only in the template. The builder refuses to publish a payload carrying it. |

`spendCounts` appears in older payloads. **The shell never read it** — don't
collect it, and drop it when you find it.

## `projects[]`

```json
{"key": "wsf", "name": "Footscray Whitehall", "code": "WSF0017",
 "c": "8073cf06-510b-4844-b486-432afb16cfbc"}
```

All four are required. `key` is the short handle every record's `p` points at.
`c` is the Forma container id — every deep link on the page is built from it, so
a wrong one silently produces links that go nowhere. The first word of `name` is
what the masthead stamp and the ledes use ("Footscray and Clayton").

## Every record

| Field | | |
|---|---|---|
| `p` | **required** | The `projects[].key` this belongs to. The builder refuses a key that is not in the list. |
| `id` | **required** | The Forma record uuid. The record's deep link is built from it. |
| `name` | | The record's title. |
| `amt` | | The money. Negative for a credit. |
| `status` | | Forma's own status — `draft`, `open`, `pricing`, `proposed`, `inReview`, `revise`, `executed`. |
| `with` | | Who is holding it, as Forma names them. `"Head of Delivery — Sam Delmenico"`, or several separated by `; `. `null` means nobody: the page then says "not in an approval" rather than pretending. |
| `step` | | The approval step currently running, matching an entry in `chain` — or a terminal state (`Ready to execute`, `Sent back`). |
| `chain` | **required** | The named steps in order: `["Project Lead", "Finance"]`. `[]` when nothing is running. This draws the approval strip. |
| `done` | **required** | Steps already signed off: `[{"s": "Project Lead", "by": "Gemma Coenen", "at": "3 Jul"}]`. `[]` when none. `s` must appear in `chain`. |
| `due` | | The review due date. Renders as "Review due …". |
| `age` | | Days overdue — **Forma's own count**, not a subtraction the page performs. Drives the colour: under 30 clear, 30–89 tight, 90+ over, and 90+ also greys the row as stale. |
| `note` | | One line of context under the title. |
| `contra` | | A short sentence saying this record was **settled elsewhere** — "Transferred to the Retail Reduction Deed of Variation". Flags the row and feeds the "Already dealt with" tile. The most valuable field on the page: a queue full of decisions already taken is the thing nobody notices. |
| `docs` | | `[{"n": "file name.pdf", "u": "<bare id>"}]`. See below. |
| `bud` | | The budget line. See below. |

## `variations[]` only

| | |
|---|---|
| `tier` | `pco`, `rfq` or `sco` — Potential, Submitted, Approved. Sets the label and the deep link's tier segment. |
| `num` | The variation number as Forma shows it: `CV-38`, `VARPF-0009`. |
| `priced` | On a `pco`, `true` means the amount is a quote rather than an estimate, and the label changes from "Estimate" to "Priced". |
| `novation` | `true` marks it a Deed of Novation. Counted separately in the credits tile, because a novation credit is not a saving. |

## `contracts[]` only

| | |
|---|---|
| `code` | The contract number: `WSF0017-0001`. Its presence is what tells the shell this is a contract. |
| `vendor` `abn` | The counterparty. `null` vendor is normal on a draft. |
| `type` | The cost type: `3000-PROFESSIONAL FEES`. |
| `invoiced` | Invoiced to date. Against a contract that is not `executed` this feeds the "Invoiced, not executed" tile — money already claimed on a contract Forma does not show as signed. |
| `scope` | The scope of work as prose, inside the dropdown. |
| `sov` | The schedule of values. `[{"code": "...", "name": "...", "amount": 0, "stages": [{"code": "...", "name": "...", "amount": 0}]}]` — fee stages **sum to their line** rather than adding to it, which is what the dropdown's footnote says. `[]` renders "No schedule of values. Nothing can be claimed against it until one exists." |
| `ins` | `{"pi": 10000000, "pl": 20000000}` — professional indemnity and public liability minimums. |
| `locked` | `true` when NetSuite is mid-sync. Shows as a blocker: a write referencing it may be refused. |
| `compliance` | `"pending"` or `"compliant"`. Pending shows as a blocker. |
| `terminated` | `{"by": "...", "at": "18 May 2026"}` — sent back rather than approved. |

A contract with no SOV, a `locked` flag or pending compliance is drawn as
**blocked**: it cannot progress whoever approves it, which is a different
problem from being slow.

## `invoices[]` only

| | |
|---|---|
| `num` | The NetSuite vendor bill: `VENDBILL21130`. |
| `entity` | Who is billing. |
| `title` `ref` | The invoice's description and the supplier's own reference. |
| `contract` | The contract code it is claimed against, if any. |

On Spend the **budget track leads** and the approval chain follows, because the
question an invoice asks is whether there is headroom, not who is holding it.
The cap is whichever of `revised` and `committed` is **lower** — an invoice can
sit inside a generous commitment and still break its line.

## `bud`

```json
{"code": "17132.11103", "name": "Land Tax - current", "revised": 1880859.63,
 "committed": 1880859.63, "spent": 624521.31, "queued": 714025, "queuedN": 1}
```

`queued` is everything waiting on that line — not just this record — and
`queuedN` how many records that is. Two records on one line both show the same
line's full exposure, which is the point: approving either changes the other's
position.

## `docs`

```json
{"n": "AC006_G4_WSF_Variation Approval No. 54.pdf", "u": "_qz3gO-pQZ2Ib6jzRLWPEA"}
```

**`u` is the bare id — 22 characters, no `urn:` prefix, no `?version=`, no
slashes.** The shell wraps it into a Docs link itself. The builder rejects a
whole urn here, because storing one produces a link that resolves for nobody.

Two strings per attachment. The page never carries a file.
`desk-forma-reads.md` explains where the id comes from and why the broken-looking
form of it is the one that works.
