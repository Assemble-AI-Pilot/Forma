---
name: gem-bot
description: "Gem Bot (Named after Gemini) prepares Assemble's internal Consultant Recommendation (CRC Recommendation) documents from a consultant fee proposal plus any supporting emails. Use this skill WHENEVER the user asks to prepare, draft, populate or \"do a recommendation\" / \"CRC recommendation\" / \"consultant recommendation\" for appointing a consultant, or references \"Gem Bot\" — even if they don't name the template. Typical triggers: \"Gem Bot, prepare a recommendation for this fee proposal\", \"draft the CRC recommendation for the [discipline] consultant on [project]\", \"fill out the consultant recommendation from the attached proposal\", or dropping a fee proposal PDF + email and asking for the internal sign-off doc. The output is a populated Word version of Assemble's CRC Recommendation template, ready for the user to review before issuing for signature. Do NOT use this for letters on Assemble letterhead (use assemble-letterhead-branding) or general branded documents (use assemble-brand-guidelines)."
---

# Gem Bot — Consultant Recommendation preparation

Gem Bot turns a consultant **fee proposal** (plus supporting emails) into a completed
**CRC Recommendation** — the internal document Assemble prepares to approve appointing a
consultant and to authorise preparing their consultant agreement. The finished document goes
to the project lead, then Delivery Director / CEO for signature depending on value.

## The golden rule: propose, then populate

**Do not fill the template straight away.** The user wants to review the content first. Work in
two phases:

1. **Phase 1 — Gather and propose.** Read the proposal and emails, run the entity and cost-code
   lookups, and draft an answer for *every* field. Then present a single consolidated list of
   **questions and draft answers** for the user to confirm or correct. Highlight genuine gaps and
   ask the specific questions listed below (especially the comparative-reference question for Due
   Diligence). Stop and wait for the user.

2. **Phase 2 — Populate.** Once the user confirms (or amends) the answers, write the values JSON
   and run the fill script to produce the Word document, then present it.

This matters because the judgement fields (Scope, Due Diligence, Comments, Timelines, departures)
carry the user's commercial reasoning — getting agreement on the words *before* generating the
document saves a re-do and keeps the user in control of what gets signed.

## Inputs you will be given

- A **fee proposal** (usually a PDF). The primary source.
- Optionally **emails** (.msg/.eml or pasted text) — the consultant's contact details, the RFP,
  and anything agreed since the proposal. Read these: email signatures are the best source for the
  counterparty's email and mobile.
- A **budget** figure (the user states it, or it comes from a budget sheet).
- Sometimes just a **project reference** ("the Clayton one") — that resolves the Assemble entity.

## Bundled resources

- `assets/CRC_Recommendation_Template.docx` — the blank template (do not edit in place; the fill
  script reads it and writes a new file).
- `assets/Entity_Bible.xlsx` — Assemble's entity register. Updated from time to time; if the user
  supplies a newer copy, pass it to the lookup with `--bible`.
- `assets/Consultant_Cost_Codes.xlsx` — discipline → cost code mapping.
- `scripts/lookup.py` — resolves the Assemble entity and the cost code (see below).
- `scripts/fill_recommendation.py` — fills the template from a values JSON (see below).

Install deps once per session if needed: `pip install openpyxl python-docx --break-system-packages`.

---

## Phase 1 — How to fill each field

Read the proposal and emails first, then work through the fields. Conventions that apply
everywhere: **all dollar figures are EXCL GST**; show **only the ABN** for each entity (not both
ABN and ACN); and wrap anything you are **not certain about in [square brackets]** — the fill
script highlights bracketed text yellow so the user spots it on review.

### Document for Execution
- **Project**: the project name and address, e.g. "Assemble Clayton (CRC) – part of 209–211
  Carinish Road, Clayton VIC". Take it from the proposal/RFP.
- **Discipline**: the consultant's discipline (Architect, Engineer – Civil, Town Planner, etc.).
  Use the matching cost-code name so this and the cost code line up.

### 1.a Project Entity Details (the Assemble side)
Resolve via the lookup — Assemble appoints consultants through the project's **developer** entity:

```bash
python scripts/lookup.py entity "<project search term>"   # e.g. "Carinish" or "Footscray"
```

- The lookup only returns entities whose Purpose is **Project - Developer**.
- **If it returns more than one entity, ask the user which one** — several projects (Footscray,
  Coburg, Brunswick) have multiple developer entities and you must not guess.
- **Assemble Entity / ABN**: from the lookup (ABN only).
- **Assemble Address**: from the lookup's Registered Address. If it is blank in the bible,
  **default to `19 Thompson Street, Kensington VIC 3031`** (Assemble's standard registered office).
- **Proposed Signatory**: always `Sam Delmenico under Power of Attorney and Delegation of Authority`
  (pre-filled in the template; leave as-is).

### 1.b Counterparty Details (the consultant)
- **Counterparty Entity**: the consultant's **legal entity** (the "… Pty Ltd" on the ABN /
  letterhead), not the trading/brand name.
- **Counterparty ABN**: from the proposal (ABN only).
- **Counterparty Address**: the address on the proposal is fine.
- **Proposed Signatory**: the person who signed the proposal (name + title).
- **Email / Mobile**: from the email signature in the supporting correspondence.

### 2. Scope
- **Scope**: 2–3 lines describing the engagement, drawn from the proposal's scope of services.
  If the proposal's scope is **highly broken down**, group it by stage rather than listing every
  sub-item. Note major exclusions briefly.
- **Timelines**: if the consultant has **confirmed they will meet the project milestones/timeframes**,
  simply state that they have confirmed they will meet the Project timeframes (cite the key dates).
  Confirming they will meet the milestones is equivalent to confirming compliance — don't over-hedge.
  If they have *not* confirmed, say so and flag it `[in brackets]`.

### 3. Financial Terms
- **Budget**: the budget figure for this discipline (ex GST). The fill script formats a number
  like `50000` as `$50,000`.
- **Budget Cost Code (Name) / (Number)**: resolve from the discipline:

  ```bash
  python scripts/lookup.py costcode "<discipline term>"   # e.g. "civil" or "structural"
  ```

  If the term is clear (one obvious match), take it. If it's ambiguous (e.g. "architect" returns
  Design / Documentation / Landscape / Heritage / Interior), **ask** which one.
- **Proposed Commitment**: use the proposal's **actual fee stages and amounts** — not the
  template's placeholder example stages. Pass them as `commitment_stages` (label + amount each);
  the script renders them aligned, with an underlined Total. The Total drives the signature logic.
  If the proposal breaks the fee into many sub-lines, group them under the stage headings.
- **Other Budget Cost Forecast**: an amount + reference if one is provided, otherwise `$0 / NA`.
- **Remaining Budget**: computed by the script (Budget − Commitment total − Other forecast).
- **Comments**: state whether the commitment is within or over budget. If **over budget**, note how
  much will be drawn from contingency. It's useful to note excluded extras (disbursements, site
  visits, optional certifications) that the remaining budget may need to absorb.

### 4. Due Diligence (Notes)
Explain how the consultant was selected. If it went to competitive tender or other proposals were
received, summarise that. If it was a **single-source / direct appointment**, explain why (e.g.
specialist scope, prior performance) and reference the consultant's relevant project experience.
**Always ask the user whether they have a comparative reference project** — e.g. another consultant's
fee on a similar scope — because that is what demonstrates value for money, and it usually isn't in
the proposal. Fold their answer into the narrative ("a comparable engineer quoted $X for a simpler
scope, so this fee represents good value").

### 5. Legal and Risk Review
- **Departures** (the row labelled "N/A"): a **numbered list** of the departures the consultant has
  requested from Assemble's standard Consultancy Agreement. Source these from the proposal's
  "terms of engagement" / contract-comments section. Include any material disclosures (e.g. a change
  of control / acquisition) as a final item. Pass as a list to `departures`.
- **Public Liability / Professional Indemnity**: the insured limits. If the proposal doesn't state
  them, this is a genuine gap — set `[To confirm – not specified in the fee proposal; request
  certificate of currency.]` so it highlights yellow.
- **Form of Agreement**: `Long Form` or `Short Form`. The proposal usually names the proforma (a
  "Major Design Consultant Agreement" is Long Form).
- **Proposed to be Novated**: `Yes`/`No`. If the proposal contemplates novation (e.g. asks to review
  novation terms), best-guess `Yes` and note it's subject to agreeing terms. If unclear, ask.
- **Design Consultant**: `Yes`/`No` (is this a design consultant?).

### 6. Attachment
- **Supporting documents checklist**: a **numbered list** of the fee proposal (with its reference
  and date) and each relevant email. Pass as a list to `attachments`.

### Recommendation for Signature (thresholds, ex GST)
- **Jarvis Mellor** — always **Yes**.
- **Sam Delmenico (Director, Delivery)** — **Yes when the commitment total > $25,000**, else No.
- **Carolyn Viney (CEO)** — **Yes when the commitment total > $1,000,000**, else No.

The fill script computes Sam/Carolyn from the commitment total automatically; only set
`sam_required` / `carolyn_required` to override.

---

## Phase 2 — Generate the document

Write the confirmed answers to a values JSON, then run:

```bash
python scripts/fill_recommendation.py values.json "<output>.docx"
```

Name the output `YYMMDD_CRC_Recommendation_<Counterparty>.docx` (today's date, e.g.
`260623_CRC_Recommendation_WGAVIC.docx`). Then present it with `present_files`.

The script removes all the yellow instruction prompts, keeps the table formatting, highlights any
`[bracketed]` notes yellow, renders the numbered lists and the aligned/underlined commitment, applies
the signature logic, and forces the signature table onto its own page.

### Values JSON schema

```json
{
  "project": "...", "discipline": "...",
  "assemble_entity": "...", "assemble_abn_acn": "ABN ...", "assemble_address": "...",
  "counterparty_entity": "...", "counterparty_abn_acn": "ABN ...", "counterparty_address": "...",
  "counterparty_signatory": "...", "counterparty_email": "...", "counterparty_mobile": "...",
  "scope": "...", "timelines": "...",
  "budget": 50000, "cost_code_name": "...", "cost_code_number": "...",
  "commitment_stages": [["Schematic Design for Town Planning", 9500], ["Design Development for Tender", 25500]],
  "other_budget_forecast": "$0 / NA", "comments": "...",
  "due_diligence": "...",
  "departures": ["...", "..."],
  "public_liability": "...", "professional_indemnity": "...",
  "form_of_agreement": "Long Form", "proposed_novated": "Yes", "design_consultant": "Yes",
  "attachments": ["...", "..."]
}
```

Any omitted field is left **blank** in the document (not left as the yellow prompt), so a blank cell
is itself a visible signal that something still needs input. After presenting, do a quick visual
check (convert to PDF and view) if anything about the layout is uncertain.
