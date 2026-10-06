---
name: forma-bots
description: "Router to Assemble's Forma bots, which ship inside the forma-user plugin. Use it WHENEVER the work is Assemble cost admin against Autodesk Forma - a consultant contract at any step (a fee proposal, a CRC Recommendation, \"appoint them\", \"their commercials are agreed\", \"send it for approval\"), a variation at any stage (\"var-bot\", \"do the approval for CV037\", \"the QS has assessed this variation\", \"we found asbestos, might cost 150k\", \"here's the price for that variation\"), the Cost & Spend Desk or Project Dashboard (\"refresh the desk\", \"the portal is stale\", \"what is on my approvals desk\"), or the scout (\"run the scout\", \"process my next steps\"). Also when someone asks what bots exist, or drops a variation claim, QS assessment or fee proposal and asks for the internal sign-off document. It names the right bot; it does not do the bot's job itself."
---

# Forma bots — which one, and why this file exists

Assemble's bots live **inside the forma-user plugin**, at `skills/<bot>/`, so
that each bot and the Forma tools it depends on install, version and upgrade as
one thing. A bot can never be newer than the tools it calls.

The cost of that is that a plugin-bundled skill is **invocable but not
advertised** — it does not appear in the skills listing, so nothing triggers it
from an ordinary sentence. This file is the trigger. It is deliberately tiny: it
holds no process knowledge of its own, because two copies of the same rules
drift and the copy in the plugin is the real one.

The plugin's `docs/skill-tree.svg` draws the whole tree.

## The bots, in two groups

Route to a **front door** only. Each front door works out the step itself and
hands over to the right step skill — never jump straight to a step skill from
here.

### Cost admin — moving Assemble's cost records through their workflow

| Bot | Invoke | For |
|---|---|---|
| **contract-bot** | `forma-user:contract-bot` | A **consultant contract**, from vendor selection to execution: the CRC Recommendation, the draft contract, the agreed terms, approval, and the agreement. Front door over `contract-vendor-selection`, `contract-vendor-approval` and `contract-vendor-execution`. Supersedes gem-bot. |
| **var-bot** | `forma-user:var-bot` | A **variation** — contractor or consultant — at any stage: flagged and estimated, priced, or recommended for approval. Front door over `variation-estimated`, `variation-proposed` and `variation-committed`. |
| **desk-bot** | `forma-user:desk-bot` | The **Cost & Spend Desk** (some people's is called Project Dashboard) — the published page of everything that has stopped moving, who is holding it and the budget line it draws on. Refreshing it, adding a project, or standing one up for a different project set. The viewer across the whole group. Reads only. |
| **scout-bot** | `forma-user:scout-bot` | The **scout**: reads Aconex (and email, once connected) for things that move a contract or variation on, and suggests the next move on the desk's Next steps tab. Also carries out "process my next steps". Never writes to Forma itself. |

Not yet built, so do not offer it: **expense-bot**. When it exists it joins this
table, and nothing else about this file changes.

### Forma information — finding things out

| Bot | Invoke | For |
|---|---|---|
| **forma-user** | `forma-user:forma-user` | A **question about project money** — what is committed, what is left, what a consultant has billed, where something is in its approval. Reading, not producing a document. |

Not yet built, so do not offer it: **forma-reporting**, which will extract set
reports in the right format.

## Routing

**Go straight to `forma-user:var-bot`** for anything about a variation, at any
stage, including all of these:

- *"var-bot, do the approval for Hacer CV037"*
- *"prepare the variation approval for the asbestos variation on Footscray"*
- *"the QS has assessed this variation, write it up"*
- *"just flagging we found asbestos, might be 150k"* — that is stage 1, and it
  should be logged even though no document comes out of it
- *"please see attached price of 143,555 for the asbestos works"* — stage 2
- *"now push that variation into Forma"*

**Go to `forma-user:contract-bot`** for a consultant contract at any step — a fee
proposal, a CRC Recommendation, "raise the consultant agreement", "appoint them",
"their commercials are agreed", "where is the [consultant] contract up to?".

**Go to `forma-user:desk-bot`** for anything about the desk, the dashboard, the
portal or the approvals page — refreshing it, why it is stale, adding or dropping
a project, or building one for another project set. It produces no document and
writes nothing to Forma; it reads, and publishes a page.

**Go to `forma-user:scout-bot`** for "run the scout", "what has moved in Aconex",
"anything in my email I should act on", and **"process my next steps"**.

**Go to `forma-user:forma-user`** for a plain question about the money.

**The line between contract-bot and var-bot:** a fee proposal for **new work** is
contract-bot; a change to work **already under contract** is var-bot. If someone
says "variation" about something that was never contracted, ask which they mean
rather than guessing — they produce different documents for different approvers.

**Do not route to any of them** for:

| Instead use | For |
|---|---|
| **forma-sov** | A schedule of values |
| **assemble-letterhead-branding** | Letters on Assemble letterhead |
| **assemble-brand-guidelines** | General branded documents |

**gem-bot is retired.** contract-bot does everything it did and then raises the
contract in Forma. If someone asks for gem-bot by name, use contract-bot and say
so.

## If the bot will not load

Every bot here needs the **forma-user plugin installed and enabled**. If invoking
one fails, say that plainly and name the plugin. Do not reconstruct the bot's
process from memory and carry on: these documents carry approval thresholds,
signature bands, insurance limits and a budget-position waterfall, and a
plausible-looking imitation of an approval document is worse than no document.
