---
name: contract-vendor-execution
description: "Step 3 of contract-bot (approved to executed): once a consultant contract is approved (Sent in Autodesk Forma), compiles the document pack into the draft agreement from Assemble's templates and checks it, ready for a person to send for signature via DocuSign from Forma. BEING BUILT - normally reached through contract-bot, which routes here for a contract at Sent."
---

# Contract vendor execution — step 3 of contract-bot

**Status: being built with the cost team, on a live Clayton (CRC0209) contract.** The compile
workflow is still to be taught. This file sets out the agreed process and what works today. Do not
improvise the parts marked *not yet*.

Read contract-bot's rules first if you came here directly. Shared files are in
`<this skill's base directory>/../contract-bot/`; the diagram is `references/contract-lifecycle.svg`
there.

## When it starts

**Once approved:** the last approver's Proceed has set the contract to **Sent** (`sent`). Forma has
no Approved status for contracts, so Sent is the approved state.

## The agreed sequence

| # | What happens | Forma status (API) | Who | Today |
|---|---|---|---|---|
| 1 | **Compile the draft**: the pack is compiled into the draft agreement from Assemble's templates, then checked against the final rec, scope and departures | stays `sent` | bot | *Not yet* — the templates and checks are still to be taught |
| 2 | **Issue via DocuSign**: the draft goes to every party for signature | stays `sent` | **a person, from Forma** | The bot never does this, for now |
| 3 | **Executed**: every party has signed | `executed` | **a person**, today | Checked 3 Oct 2026: 28 of the 32 executed contracts on Footscray and Clayton were set to Executed by a person, seconds after the final approval, and no contract records a signer. Forma sets it automatically only when its **e-signature integration** is configured (then the signed PDF is stored on the contract); nothing shows it is. A project admin can confirm in Cost Management **Settings → E-signature** |
| 4 | **Closed** when the engagement ends | `closed` | a person | — |

**Document pack:** the agreement.

## What to do today

1. Confirm the project and the contract, and that it is at `sent`.
2. Gather what the agreement will be built from: the final rec, final scope and final contract
   departures attached in step 2, and the agreement type (the **Agreement Type** attribute).
3. Tell the user the compile step is being built, and that issuing through DocuSign stays with a
   person in Forma.
4. If the contract shows `executed`, report it with the date. Approval lands as Sent and Forma
   stamps `sent_at`, `approved_at` and `awarded_at` with the final approval's time, so a contract
   that went to Executed seconds later was executed by hand, not by a signature.

## Why a person sends it, for now

Sending the agreement for signature is the point where Assemble commits to the vendor. Until the
cost team has seen the bot compile and check agreements reliably, a person reviews the draft and
sends it from Forma. This will be revisited.

## What you cannot do, and must not imply

Send anything for signature, set Executed or Closed, or edit the vendor. Never say an agreement has
been issued or signed unless Forma shows it.
