# Forma mechanics — the calls, in order

Read this when you are actually pushing a variation into Forma. `SKILL.md` carries the judgement
(what goes in which field, what to say, when to stop); this carries the endpoints, the payload
shapes and the traps. Nothing here is a decision — if you are still deciding, you are in the
wrong file.

Everything below has been run against live projects. Dates are when it was last proven.

### The five things that go up

| # | What | How |
|---|---|---|
| 1 | The Potential Variation | `forma_draft_variation`, or `POST /change-orders/pco` |
| 2 | Scope of Works | `PATCH /change-orders/pco/:id` — Tiptap **as a string**, see below |
| 3 | The amount, as ONE cost item | `POST /cost-items` — the SOV line |
| 4 | The budget transfer | `forma_draft_transfer` |
| 5 | Supporting documents **and the rec sheet** | 3-call attachment sequence, see below |

Only 1 and 4 have curated tools. **2, 3 and 5 need `forma_request` from the forma-admin plugin**,
which is normally disabled — say so rather than implying the curated tools can do it.

### 1. The Potential Variation

```
forma_draft_variation
  container_id   = <project>
  name           = what the variation IS, readable in a register. Do NOT prefix the consultant
                   or contractor — their name and contract are already shown against it, so
                   "Taylors - Item A1.1 Combined Plan of Subdivision" wastes the field.
                   "Combined Plan of Subdivision Adjustment" is the shape to aim for
  type           = from forma_project_profile, THIS project
  description    = the Purpose / Objective text, with the leading "This document seeks approval
                   to accept" stripped — so it reads as the variation, not as the memo
  contract_id    = the contract this commits against
  days_extension = only if an EOT is actually claimed
  confirm_write  = true
```

There is **no number field** — change orders number themselves. `description` caps at 2048 chars.

### 2. Scope of Works — Tiptap, and it must be a STRING

`scopeOfWork` is Tiptap rich-text. **Send it as a JSON string, not as a JSON object.** An object
is rejected outright:

```
PATCH …/change-orders/pco/:id   {"scopeOfWork": {"type":"doc", …}}
  -> 400 ValidationException
PATCH …/change-orders/pco/:id   {"scopeOfWork": "{\"type\":\"doc\", …}"}
  -> 200
```

This cost a wasted call on 17 Sep 2026 and was wrong in this file for a day. The reason the object
shape looked right is that **the readers flatten it** — `forma_variation_detail` returns
`scope_of_work` as plain prose, and a raw GET returns the string. Neither shows you the write
shape. A shape confirmed by reading is not a shape confirmed by writing.

The inner document, one paragraph node per point:

```json
{"type":"doc","content":[
  {"type":"paragraph","attrs":{"textAlign":"left","marginLeft":null,"textIndent":null},
   "content":[{"type":"text","text":"<first point>"}]},
  {"type":"paragraph","attrs":{"textAlign":"left","marginLeft":"","textIndent":""},
   "content":[{"type":"text","text":"<second point>"}]}
]}
```

`note` is the same — Tiptap, sent as a string.

**`scopeOfWork` is also accepted on CREATE**, on `POST /change-orders/:tier`, which makes stage 1
one call instead of two. `forma_draft_variation` does not expose it, so through the curated tool
you still need the PATCH. Proven on the sandbox, 17 Sep 2026.

### 3. The amount — always exactly one cost item

`forma_draft_variation` has no amount field; the money lives in a cost item. **One line item,
always.** Verified against WSF's own open PCOs:

```
POST /cost/v1/containers/:id/cost-items
  name          = the budget line name (e.g. "Survey - Land") — that is the house convention
  changeOrderId = the PCO's id     # cannot be reassigned later, so get it right
  budgetId      = the cost line
  contractId    = the contract
  committed     = the amount
  quantity = 1, unit = "EA"
```

**`changeOrderId` works but does not echo back.** The POST response omits it and a GET on the
cost item omits it, which looks exactly like a silently-discarded field. It is not — verify with
`GET /change-orders/pco/:id?include=costItems` and the item will be there. Proven on WSF,
17 September 2026, closing an open question in the corrections file.

**Which money field depends on the stage** — `estimated`, then `proposed`, then `committed`. At
stage 3 Assemble populates `committed` and leaves the rest null, confirmed across WSF's open PCOs
(one rejected credit carries `proposed`). Note that `submitted` and `approved` are not used here at
all, and that the same five fields exist on the change order itself where Autodesk marks them
"Not relevant" — the money lives on the cost item.

### 3b. Two fields the cost item needs that are easy to miss

**`scheduleChange` lives on both objects.** Setting it on the change order leaves the Scope Item
panel showing Schedule Change blank, because that panel reads the cost item's own field. Patch
both: `PATCH /change-orders/:tier/:id` and `PATCH /cost-items/:id`, each `{"scheduleChange": 0}`.

> **Fixed in the plugin, 18 Sep 2026.** `forma_draft_variation` and the stage tools
> `forma_raise_variation_estimated` / `_committed` now send `scheduleChange` on create - defaulting
> to **0** when no EOT is claimed - on the change order *and* the Scope Item. Previously an omitted
> `days_extension` meant the field was never sent at all and stayed null, so every variation draft
> raised through those tools showed Schedule Change blank. `forma_amend_draft_variation` is
> deliberately still gated: a partial amend must not overwrite a field the caller did not mention.
> If you assemble the calls by hand through `forma_request`, you still set it yourself.

**The cost item's `Type` attribute follows the waterfall.** On Footscray it offers *Budget
Transfer* and *Contingency*, and it maps onto Position against Budget exactly:

| Position against Budget | Type |
|---|---|
| Within Budget | `Budget Transfer` |
| Drawn from Project / Construction Contingency | `Contingency` |

So derive it from the same decision, do not ask twice. Set it with a **bare array**:

```
POST /cost/v1/containers/:id/property-values:batch-update
  [{"associationId": "<cost item id>", "associationType": "CostItem",
    "propertyDefinitionId": "<Type, from forma_project_profile>", "value": "Budget Transfer"}]
```

To verify, read it through the parent change order — `?include=costItems,attributes` — and look
under **`properties`**, not `attributes`. `attributes` comes back null and
`GET /property-values` is a 404, so the obvious checks all report a good write as failed.

### 4. The budget transfer

Via `forma_draft_transfer` on the everyday plugin, or by raw call. Two traps if raw:
**`budgetId` is the DESTINATION and `relatingBudgetId` the SOURCE** — the reverse of what the
names suggest — and the body is a **single object**, unlike `workflows/actions` which wants a bare
array. One POST writes a double-entry pair sharing a `transactionId`. Budget aggregates are
eventually consistent, so a read straight afterwards may still show zero pending; retry before
concluding anything failed.

```
forma_draft_transfer
  container_id  = <project>
  from_budget   = the funding source — CONFIRM IT, it is not always contingency
  to_budget     = the line bearing the cost — confirm this too
  amount        = the positive shortfall
  note          = the variation reference
  confirm_write = true
```

Created **pending**; it moves neither budget until approved in Forma.

### 5. Attachments — the rec sheet AND the supporting documents

Three calls, proven against live Clayton on 12 Sep 2026 (for a Contract; a PCO associates as
**`FormInstance`**, which is the wrapper over PCO/RFQ/RCO/OCO/SCO):

**Use `forma_attach_document` — do not hand-roll this.** It is seven calls across three Autodesk
APIs and the tool does all of them, then verifies by reading the record's attachment list back:

```
forma_attach_document
  container_id  = <project>
  file_path     = absolute path on this machine
  attach_to     = "FormInstance"        # "Contract" for a contract
  record_id     = the PCO's id
  display_name  = what it should be called in Forma (defaults to the filename)
  confirm_write = true
```

**Proven on WSF, 17 Sep 2026**, for a PCO: rec sheet and supporting email both attached, seven of
seven steps, verified.

> ✅ **Fixed in the tool since.** `forma_attach_document` now registers the **version** urn
> (`fs.file:vf.…?version=1`) and only falls back to the lineage urn with a warning
> (`tools.py`, the attach step). The note below is kept because a hand-rolled attachment, or one
> made before the fix, still needs the repair.
>
> ⚠️ **Known bug, 17 Sep 2026: the attachment uploads but cannot be downloaded.**
> Step 7 of `forma_attach_document` passes the **lineage** urn (`urn:adsk.…:dm.lineage:XXXX`)
> from the `POST /items` response. Forma stores it, the row appears, `status` is `Complete` and
> `errorInfo` is null — but the UI cannot resolve it and shows *"Couldn't download the document.
> It may have been deleted in Forma Data Management or you don't have permission to download
> it."* Every attachment that works carries a **version** urn instead:
> `urn:adsk.…:fs.file:vf.XXXX?version=1` — same id, different form.
>
> Until the tool is fixed, repair it afterwards (no re-upload needed, the file is fine):
> ```
> POST   /cost/v1/containers/:id/attachments     # same folderId, name, association;
>                                                # urn = fs.file:vf.<same id>?version=1
> DELETE /cost/v1/containers/:id/attachments/:badId
> ```
> Diagnose by comparing the urn form against any older attachment on the project — if yours says
> `dm.lineage` and theirs says `fs.file:vf`, that is the whole fault. Do not go looking at
> permissions, and do not conclude the upload failed: check `storageSize` on the Docs tip
> version, and it will match the bytes exactly.

Two things to know. `display_name` is worth setting — **the filename is the record's identity in
Docs**, so a duplicate name is a clash and a revision needs a new name. And **Docs permissions are
separate from Cost permissions**: a 403 at the storage step means the person lacks a Docs
permission, not that their sign-in is broken. Never tell them to sign in again for that.

> Do **not** reach for `forma_request` here. It sends `json_body` only, so the binary `PUT` to the
> signed S3 URL (step 4) is impossible through it — which makes attachments look blocked when they
> are not. Reading them back *is* a plain call:
> `GET /cost/v1/containers/:id/attachments?filter[associationId]=<record id>` — the same shape for
> a variation, a contract or an expense.

> **Attach to the Potential Variation, never the Approved Variation.** Attachments are filed in
> Docs under the *record's company*. A PCO has no company, so its files land in the developer's
> own folder (`WSF-(Assemble)-Ltd` on Footscray). An SCO or RFQ carries the **vendor's** company,
> so its files land in the vendor's folder — and on projects where
> `autoGrantFolderPermission` was ever on, that vendor holds View+Download+Upload on it.
> Putting Assemble's internal recommendation on an Approved Variation hands it to the vendor it
> is about. Confirmed on WSF0017, 17 Sep 2026.

Upload **both** the rec sheet .docx and each supporting document listed on it, **onto the
Potential Variation only**. The scope item has its own separate attachment set; leave it at zero. The
variation is what gets approved, so that is where the evidence belongs (Jarvis, 17 Sep 2026). Two traps: the
region appears in URNs as **`wipprodanz`**, not the `wipprod` in Autodesk's docs, so **never
hardcode a URN — read it back**; and `attachment-folders` answers POST but **404s on GET**, so its
absence from a probe means nothing. Step 2 needs Data Management scope, which requires the app to
be registered as a Custom Integration on the hub — the likeliest point of failure.

### 5b. Compliance documents — researched 3 Oct 2026, not built

Assemble wants the stage 3 recommendation uploaded as a **compliance document** rather than a
general attachment. What was found:

- **Where compliance requirements exist.** Project admins create them in Settings. *Document*
  requirements apply to **Contracts** and **Cost Payment Applications** (Cost settings) and to
  **OCOs, RFQs and SCOs** (Change Order settings). **PCOs and expenses have none.** A requirement
  shows Compliant / Pending / Not Applicable / Not Required, can **block** Send or Submit, and is
  limited to a contract type. Autodesk help: *Cost Management → Compliance Requirements* and
  *Change Order Setup*.
- **Reading them: partly possible.**
  `GET /cost/v1/containers/:id/attachments?filter[associationId]=<id>&include=complianceRequirement`
  is documented to return the compliance documents related to each attachment. What it returns has
  not been tested. No endpoint lists the requirement templates, or which requirements apply to a
  record. A contract's `complianceStatus` is readable; filtering on it is silently ignored.
- **Writing them: nothing documented.** `POST /attachments` has no requirement field and no
  compliance association type, and Autodesk's live documentation index (checked 3 Oct 2026) has no
  Compliance section for Cost Management. An undocumented route is possible but unknown.
- **What the web UI does.** The SCO's details panel → **Compliance Requirements** → **Add
  Document** next to the requirement, with three options: *Select Existing Documents*, *Upload from
  your Computer*, *Attach from Forma Data Management*. Once linked, the document is marked as
  referenced by the requirement.

**The conflict to settle before building:** a compliance document would sit on the **SCO**, whose
files land in the vendor's Docs folder — exactly what the rule above forbids for the
recommendation. Worth testing first, on the sandbox with a person signed in: can *Select Existing
Documents* pick a file already attached to the PCO, and does it copy the file or only point to it?
If it only points, var-bot can keep uploading to the PCO and the link can be made without moving
the file. Watch the browser's network calls while doing it (filter on `cost/v1`) to find the route
— it may also refuse this plugin's token, as `workflow-definitions` does (403).

---

## Stages 1 and 2, proven call by call

Run end to end against the sandbox (Implementation Hub, CON1234) on 17 September 2026 — the
asbestos case. Every call below returned what is shown and was read back. Project ids and types
are that project's; `type` is a per-project value and must come from `forma_project_profile`.

### Stage 1 — Estimated

```
forma_draft_variation                                    -> 201, CON0001, costStatus draft
PATCH  /change-orders/pco/:pco    {scopeOfWork: "<string>"}          -> 200
POST   /cost-items                {name, changeOrderId, budgetId,
                                   contractId, estimated}            -> 201
POST   /property-values:batch-update [{associationId, associationType:
         "CostItem", propertyDefinitionId, value}]                   -> 200
forma_attach_document  attach_to=FormInstance, record_id=:pco        -> 7/7
  then repair the urn — see §1, still live
```

Leave it at `draft`. No transfer, no document.

### Stage 2 — Proposed

```
GET    /workflows?associationType=PCO&associationId=:pco   -> currentStep draft, action "open"
POST   /workflows/actions  [{action:"open", associationId::pco,
                             associationType:"PCO"}]                 -> 200 echo
GET    /workflows…                                 -> open; Generate:Contract|SCO|RFQ available

POST   /change-orders/rfq  {name, type, scope, contractId,
                            sourceId::pco, description}              -> 201, costStatus draft
POST   /cost-items:attach  [{changeOrderId::rfq, costItemId::item}]  -> 200 echo
PATCH  /cost-items/:item   {proposed: <price>}                       -> 200
PATCH  /change-orders/rfq/:rfq  {scopeOfWork: "<string>"}            -> 200
PATCH  /change-orders/pco/:pco  {description, scopeOfWork}           -> 200  ← see below
forma_attach_document  attach_to=FormInstance, record_id=:pco        -> 7/7, then repair

POST   /workflows/actions  [{action:"open",    …, associationType:"RFQ"}]   -> 200
POST   /workflows/actions  [{action:"pricing", …}]                          -> 200
POST   /workflows/actions  [{action:"propose", …}]                          -> 200
```

### The SCO's ordering rule

Stage 3 has one ordering constraint that stage 2 does not, and it bites precisely because the two
tiers look symmetrical:

```
PATCH /cost-items/:item  {committed: <amount>}          FIRST
POST  /cost-items:attach [{changeOrderId::sco, ...}]    then
```

Reverse them and Forma refuses with `450238 Cannot attach cost items to the SCO because the
committed value of a cost item must not be null.` On the **RFQ** tier the reverse order works
fine, which is how this got written the wrong way round in the first place.

If it is missed, the Approved Variation exists, looks entirely normal and is worth **zero**, while
the Scope Item still carries the money against the earlier tier. See PLUGIN-BUGS §18.

### Nine things this run established

1. **One cost item genuinely sits on two change orders.** `filter[changeOrderId]` returns the
   same id for both the PCO and the RFQ after the attach. Autodesk's "cannot be reassigned to a
   different change order" means it cannot be *moved*, not that it cannot be shared — which is
   what the one-Scope-Item design depends on, and it was never tested before today.
2. **`estimated` and `proposed` coexist.** Setting `proposed` leaves `estimated` untouched, so the
   item keeps its own history. Do not clear the earlier field.
3. **`changeOrderId` is never echoed on a cost item** — not in the 201, not on a later GET. The
   association is real; it is only visible through `filter[changeOrderId]`. Do **not** put
   `changeOrderId` in a `forma_verify_write` expectation: it will report a silent discard that did
   not happen.
4. **The RFQ ladder is three separate actions** — `open`, `pricing`, `propose` — each its own call
   in sequence. You cannot jump to `propose`. Nothing in it is supplier-facing.
5. **`pricingOrRevising` carries `needApproval: true`.** That is the step's *capability*, not a
   statement that an approval will fire. With no RFQ approval workflow configured on the project,
   `propose` is offered directly and no one is notified. If a project ever gets one configured,
   this step is where it would bite — read `currentStep.actions` rather than assuming.
6. **`propose` carries `skipTransaction: true`.** No budget transaction is raised at this tier,
   which is why stage 2 needs no transfer.
7. **Proposing the RFQ drags the parent PCO to `proposed` as well** (its `budgetStatus` stays
   `open`). Do not drive the PCO's status separately at stage 2 — it follows.
8. **A PCO at `proposed` still accepts a PATCH.** So the draft-only guard in
   `forma_amend_draft_variation` is over-restrictive rather than protective — see PLUGIN-BUGS §13.
9. **RFQ numbers carry no type prefix.** The PCO came back `CON0001` and the RFQ `0001`. Quote the
   tier alongside the number or a register reads ambiguously.

### And one process lesson

After stage 2 the PCO's own `description` still read *"no price has been sought"*. It was true when
written and false an hour later. **Stage 2 must refresh the PCO's narrative, not only the RFQ's** —
the PCO is the record people open first and the one the documents hang off, so it is the one that
must never assert something stale. Keep the discovery history in it and add what changed.
