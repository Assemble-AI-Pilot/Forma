# Forma User - Assemble's cost management

> **Autodesk's Forma APIs are marked Beta** and still changing — the Cost API was
> gaining features as recently as May 2026. Something that worked last month may
> behave differently today. The sister **forma-admin** plugin's
> `docs/forma-api/02-FIELD-VERIFIED-CORRECTIONS.md` records the places where
> Autodesk's own documentation is wrong, and that list is still growing.

## Already have an earlier version? Read this, not the install steps

Upgrading is a different job from installing, and most of what follows does not
apply to you.

|  | Fresh install | Upgrade |
|---|---|---|
| Install Python | yes | **no** - already there |
| Sign in again | yes | **no** - the sign-in lives in `~/.forma-mcp/`, outside the plugin |
| Get the app provisioned | must be done | already done |
| Start a new conversation | nice to have | **essential** |

**Remove the old version first - do not unzip over the top.** An over-the-top copy
leaves behind every file the new version dropped, and a stale module that still
imports is a miserable thing to debug.

**Then start a NEW CONVERSATION.** This is the step people skip and it is the one
that matters. The old server keeps running with the old code loaded and answers
until the conversation ends - so you can remove the old version, install the new
one, see absolutely no change, and reasonably conclude the upgrade failed.
Reopening the app usually *resumes* the same conversation and does not help.

**Confirm it worked:** run the diagnostics tool and read `plugin_version`. If that
field is missing entirely, you are still on the old build.

Autodesk **Forma** here means **ACC Cost Management**, which is what Assemble
calls Forma. Autodesk's own product named Forma is an unrelated urban-design tool.

## The skills

`docs/skill-tree.svg` draws the whole tree, with what is built and what is not.
Two groups:

**Cost admin** — moving Assemble's cost records through their workflow. Each bot
is a front door that works out the step and hands over to the step skill.

| Front door | Steps | |
|---|---|---|
| **contract-bot** | `contract-vendor-selection` → `contract-vendor-approval` → `contract-vendor-execution` | A consultant contract, from the CRC Recommendation to the signed agreement. Step 1 is built; steps 2 and 3 are being built. `skills/contract-bot/references/contract-lifecycle.svg` |
| **var-bot** | `variation-estimated` → `variation-proposed` → `variation-committed` | A variation, from a flagged estimate to the Variation Approval. All three built. `skills/var-bot/references/variation-lifecycle.svg` |
| **desk-bot** | — | The Cost & Spend Desk: one page of everything that has stopped moving. Reads only |
| **scout-bot** | — | Reads Aconex (and email, once connected) and suggests next moves on the desk's Next steps tab |
| expense-bot | — | Not built yet |

**Forma information** — finding things out.

| | |
|---|---|
| **forma-user** | Questions about project money — what is committed, what is left, what a consultant has billed |
| forma-reporting | Not built yet |

Plugin skills are invocable but not advertised, so the small **router** in
`router/forma-bots/` is what makes them fire from an ordinary sentence. INSTALL
section 8 says where to copy it.

## What it can and cannot do

It **reads** budgets, contracts, variations, expenses, progress claims and
contingency. It **writes** in a deliberately narrow way: it creates and amends
**draft** contracts and **draft** potential variations, links budgets, adds fee
stages, attaches documents, raises pending budget transfers, and runs each bot
step as one confirmed call.

Three limits are **structural** - enforced in the server, asserted by its own
tests, not a matter of policy or prompting:

| | |
|---|---|
| **Moves a record only by workflow rule** | no write tool accepts a `status`. A record moves one step only where `client.WORKFLOW_RULES` declares it — the steps Assemble's mapped process gives to a bot, each measured on the sandbox first. Today that is the internal pricing walk of a variation, which notifies nobody. Sending into approval, approving, executing and closing stay human actions in Forma |
| **Cannot delete anything** | the capability is absent, not gated |
| **Cannot touch the NetSuite link** | integration-owned fields are refused, as is deleting a synchronised record |

Plus two gates on every single write:

* **`confirm_write=true` on that specific call**, after telling you what it will
  create or change and **in which project**
* **project confinement** - off by default (`FORMA_ALLOWED_CONTAINERS="*"`), so a
  confirmed write lands wherever it is aimed, in production. Set
  `FORMA_ALLOWED_CONTAINERS="<uuid>,<uuid>"` in the server's environment to allow
  only those projects

And a property that holds however the code is later changed: **no write may be
undeclared.** A tool that changes anything must register itself as a write; a
mutating request that did not come from one raises rather than reaching Forma. A
tool registered as a *read* whose own source issues a write cannot register at all.

Every write attempt is logged to `~/.forma-mcp/write-log.jsonl`.

**A 2xx is not proof.** Forma returns success for fields it silently discards, so
every write here reads the record back and reports the comparison.

## Use

```bash
python3 login.py            # sign in to Autodesk
claude --plugin-dir .
```

## What it will not do

Approve, reject or pay anything; send a contract or an Approved Variation into
approval; execute or close a record; write to an invoice or a vendor; or delete
anything. Asked to, it says plainly that it has to be done in Forma and offers to
draft the detail. It will never imply something has been recorded.

## Two things worth knowing

**Access is not involvement.** The project list returns everything you *can* see,
including projects you have nothing to do with. Never read it as "the projects
someone works on".

**Nothing is the same between projects.** Contract types, budget code structure
and custom attributes are configured per project and genuinely differ - Clayton
has 16 contract types, the sandbox has 7, and Footscray carries two custom
attributes Clayton does not. The tools read configuration at run time rather than
assuming it.

## Tests

```bash
python3 -m forma_mcp.server --selftest
```

## For whoever maintains it

* **Never write a dollar sign followed by a digit in a `SKILL.md`.** Claude Code
  substitutes `$0`, `$1`, … in a skill with the words the user typed after the
  skill's name, so a signature threshold written that way reads as nonsense. Write
  amounts without the sign (`over 25,000`), or say "dollars". References, scripts
  and templates are not affected.
* **Adding a workflow rule** means: draw it on the diagram as a bot step, measure
  it on the sandbox (including who it notifies), make the owning tool check its
  preconditions, add selftest cases, then add the row. The comment above
  `WORKFLOW_RULES` in `forma_mcp/client.py` has the detail.
* **The master copy** lives in OneDrive while the GitHub repo is offline; move it
  back when the repo reconnects.

Version 0.10.1 (BETA).
