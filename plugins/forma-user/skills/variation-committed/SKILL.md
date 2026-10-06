---
name: variation-committed
description: "Stage 3 of var-bot (Committed): a variation has been recommended for approval, and this prepares Assemble's internal Variation Approval document (the \"Recommendation for Approval\"), then generates the Approved Variation (SCO) in Autodesk Forma with the committed figure, attaches the rec sheet and its supporting documents, and raises the pending budget transfer - ready for a person to send into approval. Normally reached through var-bot, which routes here for \"the QS has assessed this variation, write it up\" or \"do the approval for CV037\"."
---

# Variation committed — stage 3 of var-bot

The variation has been **recommended** — a QS, superintendent or project manager says accept it at a
figure. This stage produces the internal **Variation Approval** that authorises accepting it and
spending the money, then puts the commitment into Forma for a person to send into approval.

Read var-bot first if you came here directly: the stage table, one Scope Item for the whole life of
the variation, Assemble's words, the golden rule (ask, with draft answers), pulling numbers from
Forma, and the rules for every Forma write. Shared files are in
`<this skill's base directory>/../var-bot/` — called `<var-bot dir>` below.

| Phase | What happens | Who decides |
|---|---|---|
| 1. Interrogate and propose | Read what you were given, pull the live numbers from Forma, draft every field, then put questions *with draft answers* to the user | User confirms |
| 2. Populate | Generate the .docx and present it. **Stop here.** | User reviews |
| 3. Push to Forma | Only once the document is settled, and on a fresh confirmation | User confirms each write |

If stages 1 and 2 never happened, run `variation-estimated` and `variation-proposed` first — the
records must exist before this one builds on them.

---

## Keep it short. Seriously.

The single most common failure is writing too much. This is a one-page sign-off sheet, not a
report — the reader wants to know what it costs, whether it is funded, and why it is reasonable.

- **The top panel is the document.** Most readers look at Table 0 and nothing else. Total Cost is
  a **bare figure**. Position against Budget is **one of four states and nothing more**. Purpose
  is 2–3 lines on *what is being approved* — not the money, not the funding route.
- **Comments: two or three points.** Why the variation arose, and who outside Assemble has
  recommended it. That is the whole job. Do not restage the entire commercial history.
- **Supporting Documents: the key attachment.** Usually one. Call it **Attachment A**, not
  Annexure.
- **Raise evidence gaps in conversation, not in the document.** If the promised attachment is
  missing, or acceptance was communicated before the approval existed, tell the user while you
  are gathering. Do **not** write it into the .docx unless they ask. The approval is a commercial
  record, not a commentary on how it came about.

---

## Position against Budget — the four states

This is the line everyone reads, and it waterfalls down:

| State | When |
|---|---|
| **Within Budget** | Funded from the line itself, a budget transfer, or the cost category's own contingency bucket |
| **Drawn from Project Contingency** | Reportable |
| **Drawn from Construction Contingency** | Reportable |
| **NO BUDGET REMAINING** | Neither reportable bucket can cover it. Renders **red and bold** — it almost always means a mistake, so query it before issuing |

**Reportable contingency is Project and Construction only.** A subcategory bucket such as
*Contingency for Professional Fees* is **not** reportable, so drawing on it is still **Within
Budget**. That is where a contract's gain or loss normally settles: each contract's over- or
under-run transfers to or from its cost code category's contingency bucket, and nobody reports
that as a contingency draw.

Escalation tries the reportable bucket **matching the cost category** first — construction costs
go to Construction Contingency, everything else to Project Contingency — then the other one.

Set it with `funded_from` (`category` / `transfer` / `project_contingency` /
`construction_contingency` / `none`), or let the script infer it from the transfer sources. Only
the two reportable buckets change the state.

**The "Project and Construction Position" row always shows both reportable buckets**, whether or
not this variation touches them — it is the reportable position a reader wants regardless. Quote
**conservative** figures (projected budget, i.e. after transfers raised but not yet approved).

---

## The fields

Conventions: **all figures are EXCL GST**, and the financial block is a four-line arithmetic
proof that the variation is funded.

### Recommendation for Approval — the top panel

| Row | What goes in it |
|---|---|
| Project | Name and code, e.g. `11-19 Whitehall Street, Footscray (WSF)` |
| Reference | The variation reference and title |
| Prepared By | Whoever is putting it up |
| Total Cost | **The figure only**, e.g. eight thousand five hundred excl. GST — the script writes it with its dollar sign. Computed from `cost_required` |
| Position against Budget | One of the four states. Computed |
| Purpose / Objective | 2–3 lines: what approval is sought, for what scope |

### Key Items → Financial Terms

| Row | What goes in it |
|---|---|
| Cost Code | Code, budget line name, and the contract it sits under |
| Cost Required | The recommended cost of the variation |
| Uncommitted Budget Available | The line's **uncommitted** balance — revised budget less committed. **When revised equals committed this is zero**, and the whole variation is unfunded. Quoting the revised budget instead computes a phantom surplus and makes an unfunded variation read as covered |
| Budget Transfers | Each transfer: amount, source line, destination line. Confirm **both ends** |
| Revised Budget | Uncommitted available + transfers in. Computed. Equal to Cost Required means funded |
| Comments | **Two or three points.** Why it arose; who outside Assemble recommends it |

### Key Items → Feasibility Impact

| Row | What goes in it |
|---|---|
| Programme Impact | Extension of time claimed or not |
| Project and Construction Position | Both reportable buckets, conservative basis. Generated from `contingency` |

### Key Items → Internal Notes and Approvals

| Row | What goes in it |
|---|---|
| Delegated Authority | Value against threshold and who may approve. Computed |
| Supporting Documents | The key attachment(s), each with reference and date. **Attachment A**, not Annexure |

### Signatures

| Cost (dollars, ex GST) | Recommendation for Signature | Approval |
|---|---|---|
| up to 25,000 | The project lead | **The project lead** — may approve without higher approval |
| over 25,000 | The project lead | Sam Delmenico, Head of Delivery |
| over 1,000,000 | The project lead | Sam Delmenico **and** Carolyn Viney, CEO |

The **Approval section is always present** — a variation nobody approved is not an approval.
Below 25,000 the project lead signs both rows; that is what the threshold means, not that approval
is skipped. Override with `hod_required` / `ceo_required` only if the user says so.

---

## Generate it

```bash
python "<var-bot dir>/scripts/fill_variation.py" values.json "<output>.docx"
```

Name it `YYMMDD_<ProjectCode>_Variation_Approval_<Reference>.docx`, e.g.
`260917_WSF_Variation_Approval_Taylors_A1.1.docx`. Present it with `SendUserFile`.

The script prints the cost, the state, whether the revised budget actually covers it, who signs,
and **every cell it left blank** — an omitted field renders empty rather than as the yellow
prompt. Read that back to the user; don't let it pass silently. It also warns loudly on
`NO BUDGET REMAINING`.

### Values JSON

```json
{
  "project": "11-19 Whitehall Street, Footscray (WSF)",
  "reference": "Consultant Variation – Taylors Item A1.1 – Combined Plan of Subdivision",
  "prepared_by": "Jarvis Mellor",
  "purpose": "...",
  "funded_from": "category",
  "cost_code": "17141.03124 – \"Survey - Land\" (Taylors Consultant Agreement 1234-PF-0013)",
  "cost_required": 8500,
  "uncommitted_budget": 0,
  "transfers": [{"amount": 8500, "from": "Contingency for Professional Fees (17141.03900)", "to": "Survey - Land (17141.03124)"}],
  "comments": ["...", "..."],
  "programme_impact": "No extension of time applies.",
  "contingency": {
    "project":      {"code": "ZZZZZ.02001",  "amount": 5753952},
    "construction": {"code": "17111.05900", "amount": 9133548.14}
  },
  "supporting_documents": ["Attachment A – ..."],
  "preparer_name": "Jarvis Mellor",
  "preparer_position": "Senior Development Manager",
  "footer": "WSF – Taylors Item A1.1 Combined Plan of Subdivision – Variation Approval"
}
```

`total_cost`, `position_state`, `revised_budget` and `delegated_authority` are computed if
omitted.

---

## Then, and only then, Forma

**Finish the document first.** The user reviews and settles the .docx before Forma is mentioned at
all — do not bundle "shall I push this too?" into the same breath as presenting it.

When they are ready: show a **plain table in chat of exactly what will be created**, **name the
project**, then get a fresh confirmation.

Set `approved_in_forma: true` in the values JSON for any sheet that is going into Forma — the
Signature and Date columns then read **"Approved in FORMA"** rather than leaving empty boxes that
invite a wet signature. Approval is evidenced by Forma's workflow, not by ink.

**The tool:** `forma_raise_variation_committed` — one call, one confirmation, one audit entry for
the stage. It does **not** move the SCO past draft, and does not raise the budget transfer; the
transfer is a separate, deliberate `forma_draft_transfer`.

### What happens, in order

1. **The .docx is settled first.** Everything below waits on that.
2. Read back the PCO and RFQ and their current attachments.
3. **Detach what the recommendation supersedes** — the original estimate, an earlier quote, any
   working document the rec sheet does not cite. Leave what it does cite. Detaching removes the
   association only; the file stays in Docs, which is what "removed" means here.
4. Attach the rec sheet **and every supporting document it lists**, to the PCO.
5. Generate the SCO from the RFQ, then **set `committed` on the Scope Item BEFORE attaching
   it**. The SCO refuses an item with no committed value (`450238`), and the RFQ tier has no such
   rule — so the stage-2 order does not carry across.
6. `scheduleChange` — on the SCO **and** separately on the Scope Item. Set even when it is 0.
7. `forma_draft_transfer` — raised **pending**.
8. Stop. A person opens the Approved Variation and sends it into the approval workflow.

Read every record back after writing it and quote the comparison.

### Send starts an INTERNAL approval, not a supplier email

The SCO ladder is short — `draft → open → sent → executed` — and the `open` step carries
**`needApproval: true`**. So `send` does not notify the vendor: it routes the variation into
**`inReview`**, with an approval chain. On WSF0017 that chain is a single step, *Project Lead*.
Note `inReview` does not appear in the ladder's own `steps` list, which makes it look like an
undocumented state; it is the approval sitting between `open` and `sent`.

**The plugin cannot press Send on an Approved Variation.** No workflow rule allows it, so the
gate refuses it. Stage 3 finishes with everything populated and says it is ready; **a person sends
it in Forma.** Once sent, show who it is with:

```
forma_approval_status container_id=<project> record_id=<sco id> record_type=SCO
```

### Coming: the recommendation as a compliance document

Assemble wants the stage 3 recommendation uploaded as a **compliance document** rather than a
general attachment. **Not built**, for three reasons found on 3 Oct 2026, detailed in
`<var-bot dir>/references/forma-mechanics.md` under "Compliance documents":

- Forma's API documents no way to attach a document **to a compliance requirement** — it can only
  list which attachments are linked to one.
- Compliance requirements exist on **Approved Variations** (and contracts), **not on Potential
  Variations** — so the document would go on the SCO, which breaks the "everything on the PCO"
  rule above (SCO files land in the vendor's Docs folder).
- A project admin must first create the SCO document requirement in Change Order settings.

Until it is decided and built, keep attaching to the PCO as above, and if the user asks, say a
person can link the rec to the SCO's compliance requirement in Forma (the SCO's Compliance
Requirements section → Add Document → Select Existing Documents).

## What you cannot do, and must not imply

Send the Approved Variation into approval, move the transfer out of pending, or approve anything.
A 2xx is **not** proof — Forma returns success for fields it silently discards. Read the record
back after every write and quote the comparison; `silently_discarded` fields did **not** save.
