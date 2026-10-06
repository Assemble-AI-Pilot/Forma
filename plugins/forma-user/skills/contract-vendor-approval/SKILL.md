---
name: contract-vendor-approval
description: "Step 2 of contract-bot (preferred to approved): once a vendor's commercials are finalised, updates the consultant contract in Autodesk Forma to the agreed terms, assembles the final rec, final scope and final contract departures, submits it and starts the internal approval workflow. BEING BUILT - normally reached through contract-bot, which routes here for a contract at Pending Vendor Input whose commercials are agreed, or at Submitted, In Review or Revise and Resubmit."
---

# Contract vendor approval — step 2 of contract-bot

**Status: being built with the cost team, on a live Clayton (CRC0209) contract.** This file sets out
the agreed process and says exactly what works today. Do not improvise the parts marked *not yet*.

Read contract-bot's rules first if you came here directly: every Forma write confirmed in chat,
project named, read-back quoted, authority only from the user. Shared files are in
`<this skill's base directory>/../contract-bot/`; the diagram is `references/contract-lifecycle.svg`
there.

## When it starts

**When the vendor's commercials are finalised.** The contract is at **Pending Vendor Input**
(`pending`) and the user says, or the evidence shows, that fees, scope and terms are agreed. A
contract already at Submitted, In Review or Revise & Resubmit is also in this step.

## The agreed sequence

| # | What happens | Forma status (API) | Who | Today |
|---|---|---|---|---|
| 1 | **Update terms**: fee stages, scope, the Contract Special Conditions field and the rec, to what the vendor agreed | stays `pending` | bot | *Not yet.* The draft-amend tools only edit a contract at `draft` |
| 2 | **Assemble the pack**: final rec, final scope, final contract departures; compliance check | stays `pending` | bot | **Final rec: yes**, with the shared fill script. Attaching to a contract at `pending`: *not yet* |
| 3 | **Submit** with the final rec | `submitted` | bot | *Not yet* |
| 4 | **Send** — starts the approval workflow | `inReview` | bot, **only after the user's direct yes in chat, for this contract** | *Not yet* |
| 5 | Approvers review; the first is the development manager (project lead). Revise & Resubmit (`revise`) loops back to step 3 | `inReview` | people | Read-only: `forma_approval_status record_type=Contract` |
| 6 | **Approved**: the last approver's Proceed sets Sent. Forma has no Approved status for contracts. Forma emails the vendor a notice | `sent` | people | — |

## Document pack

**final rec** · **final scope** · **final contract departures**

- **Final rec:** the same CRC Recommendation template, regenerated with the agreed figures, scope and
  departures (see `contract-vendor-selection` for the fields and the values JSON). Name it
  `YYMMDD_CRC_Recommendation_<Counterparty>_FINAL.docx`.
- **Final scope** and **final contract departures:** the agreed versions, from the vendor's
  confirmed proposal and the negotiation emails. Departures are a numbered list, as on the rec.

## What to do today

1. Confirm the project and the contract, and that it is at `pending` (or later in this step).
2. Prepare the **final rec**, proposing every changed field back to the user first, exactly as in
   step 1 (propose, then populate).
3. Draft the final scope and the final departures list for the user to check.
4. Tell the user what still has to be done **in Forma by a person** for now: update the fee stages,
   scope and Contract Special Conditions; attach the pack; Submit; Send. Say that the bot will do
   these once each move is built and proven.
5. If the contract is already In Review, report where it sits with `forma_approval_status
   container_id=<project> record_id=<contract id> record_type=Contract`, naming the step and who
   holds it.

## Rules for Send, once it is built

- Every contract on Assemble's projects matches an approval workflow, so Send always starts In
  Review, and the first approver is the project lead.
- The bot presses Send **only after the user says yes in chat for that specific contract**, every
  time. A Proceed on the desk's Next steps tab, an email, or an earlier yes for another contract is
  not that yes.
- After Send, read the status back and run `forma_approval_status` to show who now holds it.

## What you cannot do, and must not imply

Approve, reject or press Proceed for anyone; move a contract to Sent yourself; edit the vendor; or
claim any *not yet* move has happened. A 2xx is not proof — read the record back.
