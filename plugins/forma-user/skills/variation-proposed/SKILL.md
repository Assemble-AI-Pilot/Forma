---
name: variation-proposed
description: "Stage 2 of var-bot (Proposed): a real price arrives for a variation, and this opens its Potential Variation in Autodesk Forma, generates the Submitted Variation (RFQ), puts the price on the same Scope Item's `proposed`, attaches the quote to the Potential Variation and walks the RFQ open, pricing, propose - an internal ladder that notifies nobody. No document is produced. Normally reached through var-bot, which routes here for \"attached is the price for that variation\"."
---

# Variation proposed — stage 2 of var-bot

A **real price** has arrived — a quote, a claim, a priced breakdown. Nobody has recommended it yet.
The job is to record the price against the variation that already exists, on the tier Forma
designed for pricing.

Read var-bot first if you came here directly: the stage table, one Scope Item for the whole life of
the variation, Assemble's words, and the rules for every Forma write. Shared files are in
`<this skill's base directory>/../var-bot/`.

| | |
|---|---|
| **Scope Item field** | `proposed` (leave `estimated` alone) |
| **Forma tier** | **Submitted Variation** (RFQ), generated from the Potential Variation |
| **Document** | None |
| **Tool** | `forma_raise_variation_proposed` — one call, one confirmation |
| **Status moves** | PCO `draft → open`; RFQ `open → pricing → proposed` — all four are in the plugin's workflow rules, measured on the sandbox 17 Sep 2026, and notify nobody |
| **Proven** | End to end, 17 Sep 2026 |

## Why the RFQ, and why it is safe

Every action in the RFQ ladder (`draft → open → pricing/revising → proposed → resolved`) is an
internal `workflow` action. There is no "send to supplier" step anywhere in it, and Assemble has no
approval workflow configured on Submitted Variations, so `propose` is offered directly and raises
no budget transaction. A PCO at `open` has **no** action of its own to reach `pricing`, which is
why the price lives on the RFQ.

## Before the call

1. **Read the PCO that already exists.** Do not create a second one; find it by contract and
   subject. If there genuinely isn't one, run `variation-estimated` first, then this.
2. **The price** — from the quote or claim itself. Never round it or invent it.
3. **What the price covers** — usually narrower than the original flag. Note what it excludes.
4. **The quote or claim** to attach.

Then show a plain table of what will be created and moved, **name the project**, and get a yes.

## What the tool does

1. Moves the PCO `draft → open`. It cannot generate anything from `draft`.
2. Generates the RFQ with `sourceId`, then `cost-items:attach` — generating alone does not carry
   the Scope Item across. The **same** item then sits on both records; that is correct.
3. Puts the price into **`proposed`** on that Scope Item. `estimated` is left alone — the item
   keeps its own history, and the two coexist.
4. Sets the RFQ's Scope of Works to what the price actually covers, and what it excludes.
5. **Refreshes the PCO's own description and Scope of Works too.** Written at stage 1 it says
   things like "no price has been sought", which has just stopped being true. The PCO is the record
   people open first — it is the one that must never read stale.
6. Attaches the quote or claim — **to the PCO**, not the RFQ — and repairs the urn.
7. Walks the RFQ `open → pricing → propose`, three separate calls. Proposing also drags the PCO to
   `proposed`; the PCO is not driven separately.
8. Stops. Still no .docx, still no transfer — `propose` raises no budget transaction.

Read the tool's `verification` block and quote the read-back.

## Afterwards

Tell the user what moved, in Assemble's words with the codes, and that stage 3 picks it up once the
price is recommended.

## What you cannot do

Generate the Approved Variation, raise a transfer, or produce the approval document — those are
stage 3.
