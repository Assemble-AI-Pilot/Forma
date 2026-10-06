# Reading Forma for the desk

A whole refresh of two projects — 40 variations, 23 contracts, 9 invoices, their
budget lines and 340 attachments — costs a few thousand tokens when read this
way and several hundred thousand when read carelessly. The difference is
entirely in projection and batching.

Every call here is a **read**. Never pass `confirm_write`.

## The sequence

1. **Contracts awaiting action** — `forma_contracts`,
   `status="draft,submitted,inReview,revise,sent"`.
2. **Variations** — `forma_variations` at tier `pco` with
   `cost_status="draft,open,pricing,proposed"`, and tier `sco` with
   `cost_status="draft,open,inReview"`. Include `rfq` if any come back.
3. **Invoices awaiting action** — `forma_invoices` for `inReview` and `revise`.
4. **Who is holding each one** — `forma_approval_status`. It takes
   comma-separated ids, so **batch about 14 at a time**; one call per record is
   the single most expensive mistake available here. Pass the right
   `record_type`: `Contract`, `SCO`, `PCO`, `Expense`.
5. **Each contract on the desk** — `forma_contract_detail` for its schedule of
   values, fee stages, scope, insurance minimums and the budget codes it draws
   on.
6. **Each budget code that comes back** — `forma_budget_detail` for revised,
   committed, spent and pending transfers.
7. **Attachments** — below.

## Projection

Pass `fields` on every raw request. Unprojected, one Footscray list is hundreds
of thousands of tokens, nearly all of it fields the page never shows.

## Attachments: one paged list per project, not one call per record

```
GET /cost/v1/containers/<container>/attachments
    ?limit=100&offset=<n>   fields=["name","associationId"]
```

Page through with `offset` — Footscray had 340 — then group by
`associationId` to get each record's file names. Two fields is all the page
needs.

`filter[associationId]` **takes a list**, so a targeted sweep for just the
records on the desk is one call, not forty. That discovery took a ~40,000-token
sweep down to about 6,000.

## The document link, and the urn that looks broken

Docs resolves a file from **`entityId` alone**. The `folderUrn` the Forma UI
puts in its own links is optional — which is the only reason per-file links are
possible at all, because an attachment record does not carry a Docs folder urn.
That was written off as impossible once before; it is not.

An attachment's urn comes back in one of two forms, and both reduce to the same
id:

```
urn:adsk.<region>:fs.file:vf.<id>?version=N     a healthy attachment
urn:adsk.<region>:dm.lineage:<id>               one created before PLUGIN-BUGS §1
```

Store **only the bare `<id>`** in the payload. The shell builds:

```
<base>/docs/files/projects/<container>?entityId=
       urn:adsk.wipprodanz:dm.lineage:<id>          (url-encoded)
```

Note which form that is. The **lineage** form — the one Forma itself cannot
download, the §1 bug — is the form the Docs link wants. Same id, two forms, two
different consumers.

## The record links

Verified against the live app by navigating to each record, not guessed. `/variation`
does not exist; it was the first guess and it was wrong.

```
variations   <base>/cost/changeorder/projects/<c>/changeorders/<tier>?preview=<id>
contracts    <base>/cost/cost/projects/<c>/contracts?preview=<id>
invoices     <base>/cost/cost/projects/<c>/expenses?preview=<id>
```

`<base>` is `https://acc.aus.autodesk.com`. The shell builds all three from
`projects[].c` and the record's `id` and `tier`.

## What to carry over rather than re-read

Read the current payload first. Document ids, `chain` shapes and container ids
do not change between refreshes; re-reading them is free tokens spent for
nothing. What must be re-read every time: status, `with`, `step`, `done`, `age`,
the amounts and the budget positions.

## Two things a read cannot tell you

**Whether a record is actually live.** Forma shows a variation sitting in review;
only its description, a note or someone's memory says it was settled by a deed
three months ago. That is the `contra` field, and it is the desk's most useful
column. Take it from what the record itself says — never from an assumption
about what a stale date means.

**Whether the person named is the person who should act.** `forma_approval_status`
names the step and its assignee. Only a step named to the signed-in person may
be answered by them, and nothing on this page changes that.
