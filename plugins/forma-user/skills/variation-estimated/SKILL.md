---
name: variation-estimated
description: "Stage 1 of var-bot (Estimated): someone flags a possible variation with a guess at its cost, and this logs it in Autodesk Forma as a draft Potential Variation (PCO) with one Scope Item carrying the estimate and the source attached, so the exposure is visible before anyone commits to it. No document is produced. Normally reached through var-bot, which routes here for a flag like \"found asbestos, might be 150k\"."
---

# Variation estimated — stage 1 of var-bot

Someone has flagged a **possible** variation and put a rough number on it. Nothing has been priced
or recommended. The job is to make the exposure visible on Forma's register now, so it is on record
from the day it was known.

Read var-bot first if you came here directly: the stage table, one Scope Item for the whole life of
the variation, Assemble's words, and the rules for every Forma write. Shared files are in
`<this skill's base directory>/../var-bot/`.

| | |
|---|---|
| **Scope Item field** | `estimated` |
| **Forma tier** | **Potential Variation** (PCO), left in **draft** |
| **Document** | None |
| **Tool** | `forma_raise_variation_estimated` — one call, one confirmation |
| **Proven** | End to end, 17 Sep 2026 |

## Before the call

1. **Which project** — never guess.
2. **Does a Potential Variation for this already exist?** `forma_variations tier=pco`. If one does,
   do not raise another: say so and stop, or move to the stage the evidence supports.
3. **The contract it sits against** and **the cost code**, from `forma_contracts` and
   `forma_budgets`.
4. **The estimate** — the flag's own number. If the flag has none, ask; never invent one.
5. **The source** — the email or note that raised it, to attach.

Then show a plain table of what will be created, **name the project**, and get a yes.

## What the tool does

1. `forma_draft_variation` — the PCO, left in **draft**.
2. `PATCH` the Scope of Works from the flag's own words. It says plainly that this is an estimate
   and that no price has been sought. **Tiptap is sent as a string** — an object is a 400.
3. One Scope Item, the number in **`estimated`**, plus its `Type` attribute. `scheduleChange` is
   sent as 0 unless time is claimed.
4. Attaches the source — the email or note that raised it — **to the PCO**, and repairs the urn.
5. Stops. No .docx, no transfer, no status change.

`scope_of_work` is a **list of paragraphs**, not JSON. Read the tool's `verification` block and
quote the read-back; if it stopped partway it says where, and what exists.

## Afterwards

Tell the user what now exists, in Assemble's words with the code: *"Potential Variation VARPF-0010
is on Footscray in draft, estimated at 150,000 against Taylors' contract 1234-PF-0013, with your
email attached."* (The codes here are illustrative.) Say that stage 2 picks it up when a real price arrives.

## What you cannot do

Open the PCO (that is stage 2's first move), raise a transfer, or produce the approval document.
