# Forma mechanics — raising a contract

Read this before the first Forma call of phase 3. `SKILL.md` carries the judgement — what goes in
which field, what to say, when to stop. This carries the endpoints and the traps.

Everything here has been run against a live project. Dates are when it was last proven.

## The whole sequence is one tool

`forma_raise_contract` does it in order and verifies each step. Proven end to end on the sandbox
(Implementation Hub, CON1234) on 18 September 2026, from a real WGA civil engineering
recommendation: four fee stages, root line rolled up to $43,300, recommendation attached and
downloadable.

```
forma_vendor  query=<ABN>                        -> company_uid, or a hard stop
forma_raise_contract
  POST   /contracts                              -> 201, status draft
  POST   /budgets-contracts:link                 -> 2xx, EMPTY body; creates the root SOV line
  POST   /schedule-of-values  (one per stage)     -> 201 each, parentId = the root line
  POST   /property-values:batch-update            -> the insurances and Key Personnel
  forma_attach_document  attach_to="Contract"     -> the fee proposal and the recommendation
  GET    /contracts/:id                           -> read back
  GET    /schedule-of-values/:root                -> the roll-up check
```

Doing it by hand is possible but there is no reason to; the tool exists because the *order* is what
goes wrong, not the individual calls.

## Five things that will bite

**1. The vendor must already exist on the account.** Vendors are mastered in NetSuite and pushed
down — Forma cannot create one, and neither can this plugin. Check on the **ABN**, which matches
exactly (`filter[taxId]`); name matching is contains-and-loose and will mislead you.

Proven 18 Sep 2026: **WGAVIC Pty Ltd, ABN 59 127 466 997, was absent from all 506 companies** on
the Assemble account. A real recommendation, a real appointment, and the contract could not be
raised at all. This is the first thing to check, not the last.

Account membership is enough. The vendor does **not** need attaching to the project first — the
sandbox happily accepted a contract naming a company attached to a different project.

**2. A budget line can carry only ONE contract.**

```
POST /budgets-contracts:link   on a budget already linked
  -> 400  450030  "The same budget is only allowed to be linked to one contract
                   in mode of multiple budgets to one contract."
```

The failure is clean and the message names the cause, but if you ignore it you end up with a
contract that has no budget, no root SOV line and therefore **no fee stages** — a real-looking
draft worth nothing. Check the cost code is free before you start.

**3. You cannot create a root SOV line.** It appears as a side effect of linking the budget, and
fee stages are its children. No budget link means no root line means no stages, in that order.

**4. Child SOV lines cannot be listed by any endpoint.** `filter[contractId]` returns the root
only, so counting lines always gives 1 and proves nothing. The proof that the stages landed is the
**root line's `amount`**, which auto-rolls-up from its children — compare it against the sum you
intended. That check catches a missing stage *and* a duplicated one, which a count never would.

Keep the child ids the tool returns. They are the only way to read those lines again.

**5. The insurance attributes are typed `number`.** `value` on
`property-values:batch-update` accepts strings, numbers, booleans and null — so send `10000000`,
not `"AUD 10,000,000"`. Sending text to a number-typed attribute is a `400 / 451268`. Values read
back under `properties`, not `attributes`.

## Send, and the agreed workflow

`send` on a contract is **conditional** in Forma's design:

```
send --> matches an approval workflow? --yes--> inReview -> the approvers -> sent
                                       --no---> sent
```

`sent` with no approval behind it would be a supplier-facing commitment nobody approved. The
workflow is chosen when the record is sent, by evaluating conditions at that moment, and the
endpoint that would let you read the rules beforehand is forbidden — re-confirmed 18 Sep 2026:

```
GET /cost/v1/containers/:c/workflow-definitions
  -> 403  AUTH-010  "Token does not have the privilege for this request."
```

That uncertainty is why the plugin never pressed Send. **It is now settled by Assemble's own
configuration:** the cost team confirmed on 3 Oct 2026 that **every contract matches an approval
workflow**, and the first approver is the development manager (project lead). So Send always lands
in In Review, and approval always comes before Sent. A contract-history read the same day agrees:
`sent_at` equals the final approval's timestamp on every approved contract.

The agreed process (`contract-lifecycle.svg`) therefore gives Send to the bot in step 2 —
**only after the user's direct yes in chat for that contract** — once the move has been measured
on the sandbox and added to the plugin's workflow rules (Phase B of the 0.10.0 plan). Until then,
the client refuses every contract status move, and a person presses Send in Forma.

Facts worth carrying:

- **Forma has no Approved status for contracts.** The last approver's Proceed sets `sent`, and
  Forma stamps `sent_at`, `approved_at` and `awarded_at` with that moment. Forma emails the vendor a
  notice at Sent ("for informational purposes only").
- **Request Supplier Input** (Draft → Pending Supplier Input) **emails the vendor** when they have
  collaborative permission. A bot move to Pending Vendor Input must be proven to send nothing.
- **Executed is set by a person** on Assemble's projects: 28 of 32 executed contracts on Footscray
  and Clayton were executed by hand seconds after approval, and none records a signer. Forma sets
  it automatically only when its e-signature integration is configured.
- **Never write a contract's status directly.** §56: a status write skips an approval step rather
  than answering it, and Forma records nothing. Moves happen by workflow action, and only where a
  workflow rule allows.

Once a contract *is* in review there is no bypass — only the assignee can answer it.

## Attachments

`forma_attach_document` with `attach_to="Contract"`. Seven calls across three Autodesk APIs; the
tool does all of them and verifies by reading the record's attachment list back.

Two things to know. **A contract with no supplier cannot have an attachment folder** — Forma
refuses with `404 / 450140 "Folder - supplier company not found"`, which reads as though the
contract is missing. And **Docs permissions are separate from Cost permissions**: a 403 at the
storage step is a Docs permission to request, not a broken sign-in. Never tell someone to sign in
again for that.

Check `verification.downloadable` on the result. If it is false the file uploaded but carries the
wrong urn form and will not open — see PLUGIN-BUGS §1, fixed at source on 17 Sep 2026.

## Deletes, if a test goes wrong

Both newly proven on the sandbox, 18 Sep 2026, and neither is in `forma_capabilities` yet:

```
DELETE /schedule-of-values/:id    -> 204.  The root roll-up corrects itself afterwards.
DELETE /contracts/:id             -> 204.  Frees its budget line for another contract.
```

Untested on a root SOV line, and a root line is not independently creatable — so do not assume
that one is recoverable.
