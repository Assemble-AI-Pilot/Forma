# Assemble's Forma terminology

Assemble renames much of Autodesk Cost Management to suit the Australian market. The renaming is
configured **per project** under Settings → General → Tab names and order / Additional terms, so
it can drift between projects — and the UI a person is looking at does not use Autodesk's words,
while the **API always does**. Read from this table when
someone says a word and you need an endpoint, and write back in their words, not Autodesk's.

Source: Assemble's own customisation screens, 17 September 2026.

## Tabs

| Autodesk | Assemble | What it is |
|---|---|---|
| Budget *(group)* | **Budgets** | Total incoming revenue for completing the project |
| Budget | Budget | Itemised estimate of income and expenses to deliver the scope |
| **Main Contract** | **Budget Allowance** | The primary contractual agreement, e.g. between owner and main contractor |
| Cost *(group)* | **Contracts** | Total outgoing costs to complete the project |
| Contract | Contract | A scope-of-work package, executed with external suppliers or non-contracted |
| Cost Payment Application | **Progress Claim** | Requests for payment from suppliers |
| Expense | Expense | Itemised view for processing invoices received and internal costs |
| Change Order *(group)* | **Variations** | Variation or change to works agreed in the contract |
| **PCO** | **Potential Variations** | Starting point of any budget or cost change; generates an RFQ, COR or OCO |
| **RFQ** | **Submitted Variations** | The vendor's submitted price. Renamed from "Variation Price Request" on 17 Sep 2026 |
| **SCO** | **Approved Variations** | Vendor change order — downstream cost change amending the original vendor contract |
| **Cost Item** | **Scope Items** | The individual, detailed items within a change order |
| Forecast *(group)* | **Forecasting** | Projection of remaining and final total costs |
| Cost & Time | Cost & Time | Connecting budget items with Gantt schedule items |
| Cash Flow | Cash Flow | Planned, actual and forecast costs over time |
| Performance Tracking | Performance Tracking | Tracked input against output |

## Project team terms

| Autodesk | Assemble |
|---|---|
| **Owner** | **Investor** — organisation commissioning and funding the project |
| **Main Contractor** | **Developer** — organisation appointed by clients to carry out construction works |
| **Supplier** | **Vendor** — organisations or individuals providing goods, services or raw materials |
| Approved Owner Changes | Approved Investor Changes *(status Approved or Executed)* |
| Draft Owner Changes | Draft Investor Changes *(status Draft)* |
| Executed Owner Changes | Executed Investor Changes *(status Executed)* |
| Pending Owner Changes | Pending Investor Budget Changes *(status Open, Submitted or Accepted)* |
| Pre-submitted Owner Changes | Pre-submitted Investor Budget Changes *(status Open)* |
| Submitted Owner Changes | Submitted Investor Budget Changes *(status Submitted or Accepted)* |

All of these describe **upstream budget changes** — the investor side, i.e. OCO/RCO.

## Two places the forma-user skill's glossary is wrong

Worth fixing there, because both send you to the wrong object:

1. **"Budget Allowance" is the Main Contract, not a budget line.** The forma-user table maps
   `Budget Allowance → forma_budgets → budget line`. It is actually Autodesk's **Main Contract**.
   A Scope Item's "Budget Allowance" field shows the main contract it sits under — on WSF0017
   that reads *"Investor Approved Budget"*. A budget line is just called **Budget**.
2. **"Submitted Variation" now points at the wrong tier entirely.** The forma-user table maps it
   to the SCO. Since 17 Sep 2026 the **RFQ** is named Submitted Variations and the SCO is
   **Approved Variations**, so that entry sends you one tier too far along.

Also missing from that table: **Cost Item = Scope Item**, which is the term people will actually
use when they mean the line carrying the money.

## Saying it back

When reporting, use Assemble's word and give the code or number alongside, because that is how
people find things:

> *"Approved Variation VARPF-0009 is open against Taylors' contract 1234-PF-0013, with one Scope
> Item of $8,500."*

not

> *"The SCO is open with one cost item."*
