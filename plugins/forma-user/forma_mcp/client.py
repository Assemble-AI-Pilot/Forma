"""Thin HTTP client for the three Autodesk APIs this integration touches.

The point of this module is that no tool above it should have to remember a
transport quirk. Everything Forma does differently from its documentation that
is *mechanical* is absorbed here:

  * REGION HEADERS DIFFER BY API. Cost Management wants `x-ads-region`; ACC
    Admin and Data Management want `Region`. Same value, different header name,
    and using the wrong one fails confusingly. Routed by path prefix.

  * AN EMPTY BODY CAN BE SUCCESS. `budgets-contracts:link` returns 2xx with a
    completely empty body; json.loads on it throws. Treated as `{}`.

  * A 200 CAN REALLY BE A 403. Data Management hides permission errors inside
    `meta.warnings` while returning HTTP 200 with `data: []`. A status-code check
    alone concludes "this user has no projects" and carries on. Surfaced
    explicitly as `hidden_errors`.

  * ERROR BODIES ARE STILL JSON. HTTPError bodies are parsed the same way as
    success bodies so the caller sees Autodesk's error code and detail rather
    than an exception string.

See FORMA-API-KEY.md §5.1, §7.1 and §7.2 for the evidence behind each.
"""
from __future__ import annotations

import contextvars
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from typing import Any, Callable, NamedTuple

from . import auth, config

# Path prefixes that identify which API a call belongs to, and therefore which
# region header name it needs.
_COST_PREFIXES = ("/cost/",)
_OTHER_REGION_PREFIXES = ("/project/", "/data/", "/oss/", "/construction/")

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# HOW MANY WRITES THIS PROCESS HAS ISSUED.
#
# Caches elsewhere record this number alongside whatever they cached, and
# refresh when it has moved. It exists because a long-lived server caches budget
# figures for the life of a conversation, and a variation, contract or transfer
# written in that same conversation silently invalidates them — leaving readers
# confidently quoting the figures from before the write. Found 18 Sep 2026, when
# a budget line $282,000 over was reported as having no drift at all.
#
# A counter rather than per-resource invalidation on purpose: it costs one
# refetch after any write, and it cannot be defeated by a new write path that
# forgets to invalidate anything.
WRITES_SEEN = 0


class FormaError(RuntimeError):
    """Transport-level failure. HTTP error *responses* are returned, not raised."""


class UnauthorisedWrite(FormaError):
    """A mutating request reached the client without going through the write gate."""


class NetSuiteOwned(FormaError):
    """A mutating request targeted a record NetSuite is the source of truth for."""


class LifecycleAdvance(FormaError):
    """A status move on a contract or variation that no workflow rule allows."""


class IntegrationLocked(FormaError):
    """A mutating request targeted a record an external ERP has locked."""

    def __init__(self, message: str, record: dict[str, Any]) -> None:
        super().__init__(message)
        self.record = record


# THE WRITE GATE.
#
# This server both reads and writes, so it cannot have the read-only guarantee of
# "the capability is absent". What it has instead is: NO WRITE MAY BE UNDECLARED.
#
# Once engaged, request() refuses any mutating method unless the caller passes
# authorised=True — and the only code that passes it is the write wrapper in
# registry.py, which has already checked that the tool declared itself a write,
# that the user confirmed this specific call, and that the project is on the
# allow-list.
#
# So an undeclared write is impossible in the same structural way a write was
# impossible under the read-only lock: not because the code is careful, but
# because the path does not exist. A tool that quietly constructs a POST gets an
# exception, not a record in Forma.
#
# Engaged irreversibly at server import. There is deliberately no way to disengage.
_GATE_ENGAGED = False

# Set for the duration of one declared write call by registry._authorised(), which
# runs only after the confirmation and allow-list checks have passed. A
# contextvar rather than a module flag so it cannot leak across concurrent calls.
AUTHORISED: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "forma_write_authorised", default=False
)


# An alternative source of bearer tokens, or None for the ordinary browser sign-in.
#
# This exists for exactly one caller: the full-API plugin's Secure Service Account
# mode. It is a single explicit seam rather than a config flag, so that the curated
# server — which never sets it — cannot acquire a robot identity by accident, and
# so that reading this file tells you the whole story about where a token can come
# from. Default None means forma_mcp behaves as it always has.
TOKEN_PROVIDER: Callable[[], str] | None = None



def engage_write_gate() -> None:
    """Require every mutating request to arrive through the write gate. Irreversible."""
    global _GATE_ENGAGED
    _GATE_ENGAGED = True


def write_gate_engaged() -> bool:
    return _GATE_ENGAGED


def api_for(path: str) -> str:
    """Name the API a path belongs to. Used for headers and for orientation."""
    if path.startswith(_COST_PREFIXES):
        return "cost"
    if path.startswith("/construction/"):
        return "acc-admin"
    if path.startswith(("/project/", "/data/")):
        return "data-management"
    if path.startswith("/oss/"):
        return "oss"
    if path.startswith("/authentication/"):
        return "authentication"
    return "unknown"


def region_header_for(path: str) -> tuple[str, str] | None:
    """Return the (header_name, value) this path needs, or None if it needs none.

    This is the single most easily-got-wrong detail in the whole integration:
    the two header names are different words for the same idea.
    """
    if path.startswith(_COST_PREFIXES):
        return config.COST_REGION_HEADER, config.REGION
    if path.startswith(_OTHER_REGION_PREFIXES):
        return config.OTHER_REGION_HEADER, config.REGION
    return None


def _decompress(payload: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").lower()
    if "gzip" in encoding:
        try:
            return gzip.decompress(payload)
        except OSError:
            return payload
    if "deflate" in encoding:
        for wbits in (15, -15):
            try:
                return zlib.decompress(payload, wbits)
            except zlib.error:
                continue
    return payload


def _parse_body(raw: bytes) -> tuple[Any, str | None]:
    """Return (parsed, note). An empty body parses to {} rather than throwing."""
    text = raw.decode("utf-8", "replace")
    if not text.strip():
        # Not an error: budgets-contracts:link succeeds with no body at all.
        return {}, "empty response body (this is success for some endpoints)"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return text, "body was not JSON"


def _hidden_errors(parsed: Any) -> list[dict[str, Any]]:
    """Pull real errors out of meta.warnings on an otherwise-200 response.

    Data Management returns HTTP 200 with data:[] and the actual 403 buried in
    meta.warnings. US and EMEA warnings appear even on a healthy AUS setup and
    are normal, so those are filtered out rather than alarming the caller.
    """
    if not isinstance(parsed, dict):
        return []
    warnings = (parsed.get("meta") or {}).get("warnings") or []
    if not isinstance(warnings, list):
        return []
    real: list[dict[str, Any]] = []
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        code = str(warning.get("HttpStatusCode", ""))
        detail = str(warning.get("Detail", ""))
        if code.startswith(("4", "5")) and "US" not in detail and "EMEA" not in detail:
            real.append(warning)
    return real


# THE ERP LOCK PRE-FLIGHT.
#
# Autodesk documents integrationState "locked" as "the item is currently locked
# within the ERP system, PREVENTING MODIFICATIONS until unlocked".
#
# Forma does not enforce this. Proven on the sandbox, 16 Sep 2026: an expense set
# to integrationState "locked" accepted a PATCH of its name with HTTP 200, and the
# change went through. The documented protection does not exist at the API layer.
#
# So this check is not a convenience that saves a round trip — it is the only thing
# standing between a locked record and an edit. It lives in the client rather than
# in each write tool for the same reason the write gate does: a tool that forgets
# to call it should not be possible to write.
#
# What it deliberately does NOT do is block work on merely LINKED records. Eleven
# of Clayton's twenty-three invoices carry externalSystem "NetSuite" with a null
# integrationState; approving and commenting on those is the daily job. Only
# "locked" — an ERP actively holding the record mid-sync — refuses.
# There is deliberately NO CACHE of "this record was fine a moment ago". An earlier
# version memoised the result to save a round trip, and it made the guard inert in
# exactly the case that mattered: the PATCH that SET integrationState ran its own
# pre-flight first, saw an unlocked record, cached that, and the next PATCH trusted
# the stale all-clear. A lock can be applied by NetSuite between any two calls, so
# every mutating request re-reads. One GET is cheaper than a divergent ledger.
def _lock_target(path: str) -> tuple[str, str, str] | None:
    """Return (collection, record_id, record_path) for one lockable record, or None.

    The record PATH is returned rather than left to the caller to rebuild. An
    earlier version rebuilt it by slicing the raw split, forgot that a leading "/"
    produces an empty first element, and so probed the COLLECTION instead of the
    record. A collection response has no integrationState, so the guard read every
    record as unlocked and refused nothing — while looking like it worked.
    """
    parts = [p for p in path.split("?")[0].split("/") if p]
    # /cost/v1/containers/{container}/{collection}/{id}[/...]
    if len(parts) < 6 or parts[0] != "cost" or parts[2] != "containers":
        return None
    collection, record_id = parts[4], parts[5]
    if collection not in config.LOCKABLE_COLLECTIONS:
        return None
    if len(record_id) != 36 or record_id.count("-") != 4:
        return None
    return collection, record_id, "/" + "/".join(parts[:6])


# SUBMITTING AN INVOICE FOR REVIEW — OFF BY DEFAULT, NARROWED ON IN THE FULL API.
#
# Vendor bills arrive from NetSuite in `draft` and someone has to start them before
# the project team ever sees them. That is administration, not a decision, and it
# is the one expense write worth having.
#
# It is NOT the same act as approving. Approving, rejecting, sending back for
# revision and marking paid all post an outcome back to NetSuite against the
# signed-in person's name. Those stay refused everywhere, permanently.
#
#     draft  ──submit──►  inReview  ──approve / reject / revise──►  ...
#            ^ permitted             ^ never, by either plugin
#
# Off in the everyday plugin, which stays exactly read-only on expenses. The
# full-API plugin turns it on at startup — it is the escalation surface, installed
# by a couple of people and normally disabled.
EXPENSE_SUBMIT_PERMITTED = False
EXPENSE_REVIEW_PERMITTED = False

# ADVANCING A CONTRACT OR VARIATION — permitted in the admin plugin only.
#
# §56: `PATCH /contracts/:id {"status": "executed"}` moves a contract straight to
# executed EVEN WHILE IT SITS IN AN APPROVAL WORKFLOW, skipping the step rather
# than answering it, and Forma writes NO audit entry for the skip. The action
# endpoint gives no hint this is possible — it offers only `revise` on an
# in-review contract, and the `execute` action it DOES offer is a silent no-op.
#
# So the guarantee "a draft cannot skip approval" is not something Forma enforces
# on contracts. It has to be enforced here, which is what this flag does.
CONTRACT_EXECUTE_PERMITTED = False

# Observed on Footscray: 7 expenses at inReview. `pending` is documented but has
# never been seen on real data; accepted in case a project is configured with it.
SUBMIT_STATUSES = frozenset({"inReview", "pending"})

# The outcomes. Never permitted, in any plugin, under any configuration.
DECISION_STATUSES = frozenset({"approved", "rejected", "paid", "revise"})

# Review responses proven against Forma by watching the web client, 16 Sep 2026:
#   proceed    -> the step passes, the record moves to the next one   (UI "Approve")
#   terminate  -> the step ends, status becomes `revise`              (UI "Revise")
# The UI offers a third response, Reject, whose wire value has not been observed.
# It is absent here on purpose: a guessed value would be answered 200 and ignored.
REVIEW_OPTIONS = frozenset({"proceed", "terminate"})

# Types the workflow-actions endpoint can act on that belong to NetSuite. The
# endpoint names its target in the BODY, so a path check alone misses it entirely
# — which an earlier version of this guard did.
_OWNED_ASSOCIATION_TYPES = frozenset({"Expense", "ExpenseItem"})


def permit_expense_submit() -> None:
    """Allow draft -> inReview on expenses. Called only by the full-API server."""
    global EXPENSE_SUBMIT_PERMITTED
    EXPENSE_SUBMIT_PERMITTED = True


def permit_expense_review() -> None:
    """Allow a reviewer to answer THEIR OWN review task. Admin surface only.

    This is not permission to approve an invoice. It is permission to respond to
    a task Forma has assigned to the signed-in person — the same click the web UI
    offers them. Setting an expense's status directly stays refused, and the tool
    that uses this confines itself to steps the caller is actually named on.
    """
    global EXPENSE_REVIEW_PERMITTED
    EXPENSE_REVIEW_PERMITTED = True


def permit_contract_execute() -> None:
    """Allow contract/variation status writes. Called only by the admin server."""
    global CONTRACT_EXECUTE_PERMITTED
    CONTRACT_EXECUTE_PERMITTED = True


def _refuse(kind: str, detail: str, extra: str = "") -> None:
    raise NetSuiteOwned(
        f"Refused: {detail}\n\n"
        f"{kind}s are owned by NetSuite. Assemble's finance team loads invoices "
        "there and pushes them here for approval; vendors are mastered there too. "
        f"Forma holds a downstream copy.{extra}"
    )


def _workflow_action_ok(path: str, body: dict) -> None:
    """Allow one workflow action only if Forma says it merely starts a review.

    The action NAMES are project-specific, so rather than guess at a vocabulary
    this asks Forma what the action actually does. Every action declares its
    transforms:

        GET /workflows/Expense/:id/actions
        -> [{"name": "submit", "transforms": [{"key": "status", "to": "pending"}]}]

    Judging by effect rather than by name means a project that calls its action
    "issue for approval" still works, and one that calls an approval "submit" is
    still refused.
    """
    association = body.get("associationType")
    if association not in _OWNED_ASSOCIATION_TYPES:
        return
    action_name = body.get("action")

    # ANSWERING A REVIEW TASK.
    #
    # `review` never appears in /workflows/:type/:id/actions and declares no
    # status transform, so the transforms test below cannot judge it — it would
    # fall through and be allowed by accident. It is named explicitly instead.
    #
    # What makes this safe is not this check but the caller: forma_review reads
    # the live workflow and refuses unless the signed-in person is named on the
    # step. Forma itself would happily let a project admin answer somebody
    # else's task; we do not.
    if action_name == "review":
        if not EXPENSE_REVIEW_PERMITTED:
            _refuse("invoice",
                    "answering a review task — this plugin cannot respond to "
                    "approvals.",
                    "\n\nThat belongs to the person Forma assigned it to, in Forma.")
        option = (body.get("options") or {}).get("taskOption")
        if option not in REVIEW_OPTIONS:
            _refuse("invoice",
                    f"a review response of {option!r}, which is not one this "
                    "plugin has verified against Forma.",
                    f"\n\nVerified: {sorted(REVIEW_OPTIONS)}. Anything else must be "
                    "observed in Forma's own UI before it is sent — this endpoint "
                    "answers 200 to things it ignores.")
        if (body.get("options") or {}).get("adminReviewAsCandidate") is not True:
            _refuse("invoice",
                    "a review response that is not the caller answering their own "
                    "task.",
                    "\n\nReviewing on another person's behalf is an admin override. "
                    "It is real in Forma and deliberately not wired here.")
        return

    if not EXPENSE_SUBMIT_PERMITTED:
        _refuse("invoice", f"a workflow action on {association} — invoices are "
                "read-only in this plugin.")

    record_id = body.get("associationId")
    container = (path.split("/containers/")[-1].split("/")[0]
                 if "/containers/" in path else None)
    if not (action_name and record_id and container):
        _refuse("invoice", "a workflow action without action, associationId and a "
                "container — it cannot be checked, so it cannot be allowed.")

    probe = request("GET", f"/cost/v1/containers/{container}"
                           f"/workflows/{association}/{record_id}/actions")
    available = probe.get("body") if isinstance(probe.get("body"), list) else []
    match = next((a for a in available
                  if isinstance(a, dict) and a.get("name") == action_name), None)
    if match is None:
        _refuse("invoice",
                f"Forma does not offer the action {action_name!r} on this record.",
                "\n\nAvailable here: "
                f"{[a.get('name') for a in available if isinstance(a, dict)] or 'none'}.")

    lands_on = [tr.get("to") for tr in (match.get("transforms") or [])
                if isinstance(tr, dict) and tr.get("key") == "status"]
    decisions = [s for s in lands_on if s in DECISION_STATUSES]
    if decisions:
        _refuse("invoice",
                f"the action {action_name!r} sets status to {', '.join(decisions)} "
                "— that is an approval decision, whatever the action is called.",
                "\n\nThis plugin may START a review and nothing further. Approving, "
                "rejecting, sending back and marking paid stay with a person in "
                "Forma. This is permanent.")
    if lands_on and not all(s in SUBMIT_STATUSES for s in lands_on):
        _refuse("invoice",
                f"the action {action_name!r} sets status to "
                f"{', '.join(str(s) for s in lands_on)}, which this plugin does not "
                "recognise as a submission.")


# Collections whose STATUS is a commitment rather than a field, and the status
# keys each uses. A contract answers under `status`; a variation under
# `costStatus` and `budgetStatus` (§55).
_LIFECYCLE_COLLECTIONS = ("contracts", "change-orders")
_LIFECYCLE_TYPES = frozenset({"Contract", "PCO", "RFQ", "SCO", "OCO", "RCO"})
_STATUS_FIELDS = ("status", "costStatus", "budgetStatus")

# THE WORKFLOW RULES — the only status moves this plugin may make.
#
# The plugin used to stop every contract and variation at draft, because nothing
# had been mapped. Since 0.10.0 the rule is the MAPPED PROCESS instead: the plugin
# may move a record ONE step, by workflow action, where Assemble's agreed workflow
# diagram says a bot does that step. Everything else is refused, exactly as before:
#
#   skills/contract-bot/references/contract-lifecycle.svg
#   skills/var-bot/references/variation-lifecycle.svg
#
# Each row is a measured fact, not a wish. To add one:
#   1. it is drawn on the diagram as a bot step (built or to build);
#   2. it is measured on the Implementation Hub sandbox (CON1234), including
#      who it notifies — a move that emails a vendor is not a bot step;
#   3. the owning tool checks the row's preconditions before it calls;
#   4. the selftest gains a case that allows it and one that refuses it out of
#      order — then it goes in this table.
#
# Only WORKFLOW ACTIONS are ever allowed. A direct status write stays refused for
# every record type, because of the §56 bypass: Forma will accept a status write
# on a contract inside an approval, skip the step rather than answer it, and
# record nothing in the history.
#
# DELIBERATELY NOT HERE, each for its own reason:
#
#   SCO, anything    `open` carries needApproval: true and routes the variation
#                    into a real approval chain against a real person's name.
#                    A person sends it in Forma.
#   Contract, any    not yet measured. Phase B of the 0.10.0 plan adds, one at a
#                    time and only once proven: draft -> Pending Vendor Input
#                    (only if it emails nobody), Pending -> Submitted, and Send
#                    (Submitted -> In Review, only on the user's direct yes for
#                    that contract). Approvals, Sent, Executed and Closed stay
#                    with people.
#   OCO / RCO, any   the investor side. An owner change is a commitment.
#   reject / void    a decision that a variation is dead, on any tier. A person
#                    should make that themselves; it is not bookkeeping.


class WorkflowRule(NamedTuple):
    record: str     # associationType, as the workflow-actions endpoint names it
    action: str     # the action name sent in the request body
    moves: str      # the status change it makes, in Forma's API words
    skill: str      # the step skill that owns the move
    needs: str      # what the owning tool checks before it calls
    measured: str   # where and when it was proven


WORKFLOW_RULES: tuple[WorkflowRule, ...] = (
    # Measured on the sandbox, 17 Sep 2026. The test for inclusion was Forma's own
    # `needApproval` on the step being left, plus whether anything reaches a
    # budget. Nothing in the RFQ ladder is supplier-facing; there is no "send to
    # supplier" action anywhere in it.
    WorkflowRule("PCO", "open", "draft -> open", "variation-proposed",
                 "the PCO exists, in draft. No needApproval; moves budgetStatus and "
                 "costStatus to open, so the exposure shows on the register",
                 "sandbox, 17 Sep 2026"),
    WorkflowRule("RFQ", "open", "draft -> open", "variation-proposed",
                 "the RFQ was generated from the PCO and carries its Scope Item. "
                 "No needApproval",
                 "sandbox, 17 Sep 2026"),
    WorkflowRule("RFQ", "pricing", "open -> pricing", "variation-proposed",
                 "the RFQ is open. No needApproval",
                 "sandbox, 17 Sep 2026"),
    WorkflowRule("RFQ", "propose", "pricing -> proposed", "variation-proposed",
                 "the price is on the Scope Item's `proposed`. The step carries "
                 "needApproval, but no RFQ approval workflow is configured on any "
                 "Assemble project, so `propose` is offered directly - and it "
                 "carries skipTransaction, so no budget transaction is raised",
                 "sandbox, 17 Sep 2026"),
)

# What the gate checks: the (record, action) pairs in the table. An ALLOW-LIST,
# not a hole in a deny-list - an action nobody has measured stays refused.
_RULED = frozenset((r.record, r.action) for r in WORKFLOW_RULES)
_INTERNAL_WORKFLOW_ACTIONS = _RULED   # the pre-0.10.0 name, kept for older callers


def workflow_rule(record: str, action: str) -> WorkflowRule | None:
    """The rule permitting `action` on a `record`, or None if none does."""
    return next((r for r in WORKFLOW_RULES
                 if r.record == record and r.action == action), None)


def _refuse_lifecycle(what: str, detail: str) -> None:
    allowed = "; ".join(f"{r.record} {r.action} ({r.moves})" for r in WORKFLOW_RULES)
    raise LifecycleAdvance(
        f"Refused: {detail}\n\n"
        f"This plugin moves {what} only along the steps its workflow rules allow "
        f"- the steps Assemble's mapped process gives to a bot: {allowed}. "
        "Everything else - sending into approval, approving, executing, closing - "
        "is a commitment of money in someone's name, and is made by a person in "
        "Forma, where the approval workflow can see it.\n\n"
        "This is not a limit of the API. Forma will accept a status write on a "
        "contract that is sitting in an approval workflow, skip the step rather "
        "than answer it, and record nothing in the history (§56). That is exactly "
        "why the refusal lives here."
    )


def _refuse_if_lifecycle_advance(method: str, path: str, json_body: Any = None) -> None:
    """Refuse any status move on a contract or variation that no rule allows.

    Two routes reach the same outcome and both are checked:

        PATCH /contracts/:id            {"status": ...}        the §56 bypass
        POST  /workflows/actions        [{"associationType": "Contract", ...}]

    A direct status write is refused always. A workflow action passes only when
    WORKFLOW_RULES holds a row for that record and action.

    Editing a draft is untouched: only a body that carries a STATUS key is
    refused, so forma_amend_draft_contract and friends keep working.
    """
    if CONTRACT_EXECUTE_PERMITTED:
        return
    lowered = path.lower()

    # Route 1 — the workflow action endpoint.
    if "/workflows/actions" in lowered:
        entries = json_body if isinstance(json_body, list) else [json_body]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            association = entry.get("associationType")
            if (association, entry.get("action")) in _RULED:
                continue
            if association in _LIFECYCLE_TYPES:
                _refuse_lifecycle(
                    "contracts and variations",
                    f"the workflow action {entry.get('action')!r} on a "
                    f"{association}.")
        return

    # Route 2 — writing the status field directly.
    if not any(f"/{c}" in lowered for c in _LIFECYCLE_COLLECTIONS):
        return
    if method not in {"PATCH", "PUT"}:
        return
    body = json_body if isinstance(json_body, dict) else {}
    touched = [f for f in _STATUS_FIELDS if f in body]
    if touched:
        _refuse_lifecycle(
            "contracts and variations",
            f"{method} {path} — it sets {', '.join(touched)}.")


def _refuse_if_netsuite_owned(method: str, path: str, json_body: Any = None) -> None:
    """Gate every write to an invoice or a vendor. Reads are never touched.

    Two routes reach an expense and both are checked:

        PATCH /cost/v1/containers/:c/expenses/:id          named in the PATH
        POST  /cost/v1/containers/:c/workflows/actions     named in the BODY

    The second is why this takes the body. A path-only check passed it cleanly, and
    it is the route that actually works on a project with an approval workflow.
    """
    if method not in MUTATING_METHODS:
        return
    lowered = path.split("?")[0].lower()

    # 0. Powers that arrived with the account:write scope and that nothing here
    #    needs. Closed rather than left reachable — see config for the incident
    #    that prompted it.
    if config.creates_a_project(method, path):
        raise NetSuiteOwned(
            f"{method} {path} refused: this plugin does not create projects.\n\n"
            "The account:write scope permits it, but ACC has no way to delete a "
            "project afterwards — only to mark it inactive — so an accidental one "
            "is permanent. Create projects in ACC Admin."
        )
    for fragment in config.FORBIDDEN_PATH_FRAGMENTS:
        if fragment in lowered:
            raise NetSuiteOwned(
                f"{method} {path} refused: user and business-unit administration is "
                "not something either plugin does. Reading them is fine; changing "
                "them belongs in ACC Admin."
            )

    # 1. Vendors. No exceptions, ever — NetSuite is the master, and a local edit is
    #    either overwritten on the next sync or, worse, is not.
    if "/companies" in lowered:
        _refuse("vendor",
                f"{method} {path} — vendors cannot be created or changed here.",
                "\n\nAsk finance to make the change in NetSuite; it will appear "
                "here on the next sync.")

    # 2. Workflow actions. The body is an ARRAY — a lone object is rejected with
    #    `45007 Expected type array but found type object`. Every entry is checked,
    #    so an approval smuggled in beside a submit fails the whole request.
    if "/workflows/actions" in lowered:
        entries = json_body if isinstance(json_body, list) else [json_body]
        for entry in entries:
            if isinstance(entry, dict):
                _workflow_action_ok(path, entry)
        return

    if "/expenses" not in lowered:
        return

    # 3. Expenses by the direct route. Everything refused unless this is the one
    #    permitted transition, and only where the plugin has enabled it.
    if not EXPENSE_SUBMIT_PERMITTED:
        _refuse("invoice",
                f"{method} {path} — invoices are read-only in this plugin.",
                "\n\nReading is unrestricted: status, comments, attachments, "
                "amounts, history. Report what you find and let the user act in "
                "Forma.")

    body = json_body if isinstance(json_body, dict) else {}
    parts = [p for p in lowered.split("/") if p]
    on_one_record = len(parts) >= 6 and parts[4] == "expenses"

    if method != "PATCH" or not on_one_record:
        _refuse("invoice",
                f"{method} {path} — only a status change on ONE existing invoice is "
                "permitted here. Creating, deleting and bulk operations are not.")

    if set(body) != {"status"}:
        others = sorted(set(body) - {"status"}) or ["nothing"]
        _refuse("invoice",
                f"this request changes {', '.join(others)} as well as the status. "
                "Only the status may be changed, and only on its own.",
                "\n\nAmounts, suppliers, dates and line items come from NetSuite. "
                "Send a body containing nothing but `status`.")

    status = body.get("status")
    if status in DECISION_STATUSES:
        _refuse("invoice",
                f"setting status to {status!r} is an approval decision, not a "
                "submission.",
                "\n\nThis plugin may START a review (draft -> pending). Approving, "
                "rejecting, sending back for revision and marking paid post an "
                "outcome to NetSuite against a person's name, and stay with that "
                "person in Forma. This is permanent and is not configurable.")
    if status not in SUBMIT_STATUSES:
        _refuse("invoice",
                f"{status!r} is not a status this plugin recognises.",
                f"\n\nPermitted here: {sorted(SUBMIT_STATUSES)}. "
                f"Never permitted: {sorted(DECISION_STATUSES)}.")


def _refuse_if_locked(path: str) -> None:
    target = _lock_target(path)
    if target is None:
        return
    collection, record_id, record_path = target
    try:
        probe = request("GET", record_path, max_chars=200_000)
    except FormaError:
        # The record is unreachable; the write will fail for the same reason and
        # will say so more usefully than this check could.
        return
    body = probe.get("body")
    if not probe.get("ok") or not isinstance(body, dict):
        return

    if body.get("integrationState") != "locked":
        return

    system = body.get("externalSystem") or "an external system"
    raise IntegrationLocked(
        f"This {collection.rstrip('s').replace('-', ' ')} is LOCKED by {system} "
        f"(integrationState = \"locked\"), which means that system is holding it "
        "mid-synchronisation. Changing it now can leave Forma and "
        f"{system} disagreeing about the same record.\n\n"
        "Forma itself will NOT stop this edit — it returns 200 and applies the "
        "change — so this refusal is the only protection.\n\n"
        "What to do: wait for the sync to finish and try again, or ask whoever "
        "owns the integration to release the record. Do not attempt to unlock it "
        "from here; clearing integrationState is what breaks the link.",
        {
            "id": record_id,
            "collection": collection,
            "external_system": body.get("externalSystem"),
            "external_id": body.get("externalId"),
            "locked_at": body.get("integrationStateChangedAt"),
            "last_synced": body.get("lastSyncTime"),
        },
    )


# THROTTLING, AND WHY IT CANNOT BE LEFT TO THE CALLER.
#
# Forma throttles in two different shapes and only one of them looks like an error:
#
#   429 + Retry-After          the honest form, documented
#   200 {"developerMessage":   the dangerous form, observed. No `results` key at
#        "Quota limit          all. A caller that reads `results` and finds nothing
#        exceeded."}           concludes THERE ARE NO RECORDS and answers "none".
#
# The second shape was caught once before, in the curated plugin's paging loop —
# but that left forma_request in the full-API plugin with no protection, because it
# does not page. Detection belongs here, where both plugins pass through.
#
# Retrying a 429 is safe for any method including POST: a throttled request was
# never processed. What is NOT retried is anything else — a 500 might have been.
#
# Published limits (Cost Management 300 rpm per endpoint per user; ACC Admin 600 rpm
# across all its endpoints; hq 100 rpm) are far above normal use here, so this
# exists for the shared 5,000 rpm service ceiling, which other tenants can exhaust.
THROTTLE_RETRIES = 3
THROTTLE_MAX_WAIT = 30.0


def _throttled(status: int, parsed: Any) -> bool:
    if status == 429:
        return True
    if not isinstance(parsed, dict) or "results" in parsed:
        return False
    message = str(parsed.get("developerMessage") or "")
    return "quota" in message.lower() or "rate limit" in message.lower()


def _retry_after(headers: dict[str, str], attempt: int) -> float:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    try:
        wait = float(raw)
    except (TypeError, ValueError):
        wait = 2.0 * (2 ** attempt)     # 2s, 4s, 8s
    return max(0.5, min(wait, THROTTLE_MAX_WAIT))


def request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    raw_body: bytes | None = None,
    content_type: str | None = None,
    accept: str = "application/json",
    extra_headers: dict[str, str] | None = None,
    token: str | None = None,
    authenticated: bool = True,
    max_chars: int = 20_000,
    authorised: bool = False,
    absolute_url: str | None = None,
) -> dict[str, Any]:
    """Issue one request and return a structured result.

    Never raises on an HTTP error status — the status and parsed error body come
    back in the result, because the model reading it can act on "403, you are not
    a member of this project" but not on a stack trace.
    """
    method = method.upper()
    if method in MUTATING_METHODS:
        # Bumped before the gate, not after a 2xx: a refused or failed write may
        # still have changed something, and a cache that is merely refreshed too
        # often is harmless where a stale one is not.
        global WRITES_SEEN
        WRITES_SEEN += 1
    if _GATE_ENGAGED and method in MUTATING_METHODS and not (authorised or AUTHORISED.get()):
        raise UnauthorisedWrite(
            f"{method} {path} refused: it did not come through the write gate. "
            "Every write must be issued by a tool that DECLARED itself a write at "
            "registration, and that has checked the user's per-call confirmation "
            "and the project allow-list. A tool that constructs a mutating request "
            "directly is a defect, not a shortcut — fix the tool rather than "
            "passing authorised=True."
        )
    if method in MUTATING_METHODS and not absolute_url:
        _refuse_if_netsuite_owned(method, path, json_body)
        _refuse_if_lifecycle_advance(method, path, json_body)
        if method != "POST":
            _refuse_if_locked(path)
    # An attachment upload PUTs raw bytes to a pre-signed S3 URL on a completely
    # different host, with NO Authorization header — the signature IS the
    # authorisation, and sending a bearer token as well is rejected. Routing it
    # through here anyway keeps it inside the write gate, rather than having one
    # leg of a write bypass every guard because it happens to be S3.
    if absolute_url:
        url = absolute_url
        path = absolute_url
    else:
        if not path.startswith("/"):
            path = "/" + path
        url = config.API_BASE.rstrip("/") + path
    query = {k: v for k, v in (params or {}).items() if v is not None}
    if query:
        url += ("&" if "?" in path else "?") + urllib.parse.urlencode(query)

    headers: dict[str, str] = {
        "Accept": accept,
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": config.USER_AGENT,
    }
    region = None if absolute_url else region_header_for(path)
    if region:
        headers[region[0]] = region[1]

    body: bytes | None = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = content_type or "application/json"
    elif raw_body is not None:
        body = raw_body
        if content_type:
            headers["Content-Type"] = content_type

    if extra_headers:
        headers.update(extra_headers)

    if authenticated:
        if token:
            bearer = token
        elif TOKEN_PROVIDER is not None:
            bearer = TOKEN_PROVIDER()
        else:
            bearer = auth.get_access_token()
        headers["Authorization"] = f"Bearer {bearer}"

    waited: list[float] = []
    for attempt in range(THROTTLE_RETRIES + 1):
        # urllib consumes the request object's body on send, so build a fresh one.
        http_request = urllib.request.Request(url, data=body, method=method)
        for key, value in headers.items():
            http_request.add_header(key, value)
        try:
            with urllib.request.urlopen(http_request, timeout=config.HTTP_TIMEOUT) as response:
                payload = _decompress(response.read(),
                                      response.headers.get("Content-Encoding", ""))
                status = response.status
                response_headers = dict(response.headers)
        except urllib.error.HTTPError as exc:
            payload = _decompress(exc.read(), exc.headers.get("Content-Encoding", ""))
            status = exc.code
            response_headers = dict(exc.headers)
        except urllib.error.URLError as exc:
            raise FormaError(f"Could not reach {url}: {exc.reason}") from exc

        parsed, note = _parse_body(payload)
        if not _throttled(status, parsed) or attempt == THROTTLE_RETRIES:
            break
        pause = _retry_after(response_headers, attempt)
        waited.append(pause)
        time.sleep(pause)

    result: dict[str, Any] = {
        "status": status,
        "ok": 200 <= status < 300,
        "method": method,
        "url": url,
        "api": api_for(path),
        "region_header": f"{region[0]}: {region[1]}" if region else None,
        "bytes": len(payload),
    }
    if note:
        result["note"] = note

    if waited:
        result["throttle_retries"] = len(waited)
        result["throttle_waited_seconds"] = round(sum(waited), 1)
    if _throttled(status, parsed):
        # Still throttled after every retry. This MUST NOT reach a caller as an
        # ordinary empty response — that reads as "there are no records".
        result["throttled"] = True
        result["ok"] = False
        result["error"] = (
            "Forma is throttling this request and did not yield after "
            f"{len(waited)} retries. This is NOT an empty result set — do not "
            "report it as 'no records found'. Wait a minute and try again."
        )

    hidden = _hidden_errors(parsed)
    if hidden:
        result["hidden_errors"] = hidden
        result["warning"] = (
            f"HTTP {status} but meta.warnings carries a real error. Do NOT read "
            "this as an empty result set."
        )

    if isinstance(parsed, str) and len(parsed) > max_chars:
        result["body"] = parsed[:max_chars]
        result["truncated"] = f"showed {max_chars:,} of {len(parsed):,} chars"
    else:
        result["body"] = parsed

    return result


def api_get(path: str, **kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper for the common case."""
    return request("GET", path, **kwargs)


def error_detail(result: dict[str, Any]) -> str:
    """Best-effort human-readable reason from an Autodesk error body."""
    body = result.get("body")
    if not isinstance(body, dict):
        return str(body)[:200]
    errors = body.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        first = errors[0]
        code = first.get("code") or first.get("errorCode") or ""
        detail = first.get("detail") or first.get("title") or ""
        return f"{code} {detail}".strip()
    return str(body.get("detail") or body.get("message") or body)[:200]
