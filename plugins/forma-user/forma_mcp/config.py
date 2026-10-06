"""Configuration for the Assemble Forma (ACC Cost Management) integration.

Resolution order for every setting: environment variable, then the values below.

Nothing secret lives here. The APS app "Assemble Claude Forma MCP" is registered
as a Desktop/Mobile/SPA client, which is a *public* OAuth client: it has a Client
ID and no client secret, by design (RFC 8252). The Client ID still should not be
published outside Assemble, so keep this repo private.

A NOTE ON THE NAME. Assemble says "Forma" to mean Autodesk Construction Cloud
Cost Management. Autodesk's own product called Forma (product code SPCMKR) is an
unrelated urban-design tool. Everything here means the former.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- OAuth client --------------------------------------------------------------
# Registered at aps.autodesk.com as "Assemble Claude Forma MCP",
# type Desktop/Mobile/Single-Page App (Authorization Code + PKCE).
# Also registered as a Custom Integration on the hub, which is what unlocks the
# Data Management and ACC Admin APIs — see FORMA-API-KEY.md §5.2.
CLIENT_ID = os.environ.get(
    "FORMA_CLIENT_ID",
    "pTGG8ZmJdCsNvn67Mv69YGAGsPLmQdcOjcr7zTedrxvwbXCz",
)

# --- Endpoints -----------------------------------------------------------------
API_BASE = os.environ.get("FORMA_API_BASE", "https://developer.api.autodesk.com")
AUTHORIZE_URL = f"{API_BASE}/authentication/v2/authorize"
TOKEN_URL = f"{API_BASE}/authentication/v2/token"

# The APS app has ONE registered callback URL and it is not a wildcard, so unlike
# the Aconex integration we cannot bind an arbitrary free port.
REDIRECT_URI = os.environ.get(
    "FORMA_REDIRECT_URI", "http://localhost:8080/api/auth/callback"
)
REDIRECT_PORT = int(os.environ.get("FORMA_REDIRECT_PORT", "8080"))
REDIRECT_PATH = "/api/auth/callback"

# --- Scopes --------------------------------------------------------------------
# offline_access is REQUIRED to receive a refresh token; without it the access
# token dies in an hour with no way to renew it.
#
# Scopes are ACCOUNT-WIDE, not per project. There is no way to request "write,
# but only project X" — project confinement is ALLOWED_CONTAINERS below, which is
# our discipline, not something Autodesk enforces.
# `account:write` added 16 Sep 2026 for project-settings administration.
#
# Every settings endpoint answers 403 "Token does not have the privilege" without
# it — NOT 404, so the endpoints exist and the scope is the whole blocker. Proven
# on all three projects:
#
#   PATCH /cost/v1/containers/:c/settings/:name        403
#   PATCH /hq/v1/accounts/:a/projects/:p               403
#   POST  /construction/admin/v1/accounts/:a/projects  403
#
# ANYONE ALREADY SIGNED IN MUST SIGN IN AGAIN. Scopes are fixed at consent, so an
# existing refresh token keeps the old, narrower set — which is the safe failure,
# but it means the admin tools report a missing privilege until they re-consent.
#
# This is an account-wide scope and it grants more than settings: it would also
# permit creating projects and administering users. No tool here does either, and
# the guards on vendors and invoices are unaffected by it.
SCOPES = os.environ.get(
    "FORMA_SCOPES",
    "data:read data:write data:create account:read account:write offline_access"
)
READ_ONLY_SCOPES = "data:read account:read offline_access"

# --- Region --------------------------------------------------------------------
# Assemble's hub is Australian. The two header NAMES differ per API and getting it
# wrong fails confusingly, so client.py routes by path rather than asking callers.
REGION = os.environ.get("FORMA_REGION", "AUS")
COST_REGION_HEADER = "x-ads-region"      # Cost Management
OTHER_REGION_HEADER = "Region"           # Data Management and ACC Admin

# --- Token cache ---------------------------------------------------------------
# Per-user, OUTSIDE the plugin folder, 0600.
#
# Deliberately not inside the package: a plugin folder gets zipped and handed to
# colleagues, and a token file living in it would ship with it. Keeping state here
# also means upgrading is genuinely "replace the folder" with no re-authentication.
STATE_DIR = Path(os.environ.get("FORMA_STATE_DIR", Path.home() / ".forma-mcp"))
TOKEN_FILE = STATE_DIR / "tokens.json"
WRITE_LOG = STATE_DIR / "write-log.jsonl"

# --- Known identifiers ---------------------------------------------------------
HUB_ID = os.environ.get("FORMA_HUB_ID", "d00bf4f7-61d2-4d9f-a3c1-17f7215aed8b")
# Data Management addresses the same hub and project ids with a "b." prefix.
DM_PREFIX = "b."

SANDBOX = "143038f7-6e27-4121-a78a-3e1fea149995"
CLAYTON = "d707688b-3abe-4645-bef7-ca91c6ce8fc7"
FOOTSCRAY = "8073cf06-510b-4844-b486-432afb16cfbc"

KNOWN_CONTAINERS = {
    SANDBOX: "Implementation Hub (CON1234) — SANDBOX, fake project, safe to break",
    CLAYTON: "Clayton, Carinish Rd (CRC0209) — the test project, but REAL data",
    FOOTSCRAY: "Footscray, Whitehall St (WSF0017) — LIVE",
}

# --- Write confinement ---------------------------------------------------------
# OAuth scopes are account-wide and cannot say "write, but only project X", so
# project confinement is enforced here rather than left to prompt discipline.
#
# EVERY PROJECT, FOR BETA. Opened on 16 Sep 2026 at the plugin owner's explicit
# instruction: beta testers work on their own projects, and a list naming three
# would refuse everyone else's.
#
# WHAT THIS REMOVED, PLAINLY. Project confinement was the backstop for the case
# confirmation cannot cover — a write aimed at a project nobody meant to touch.
# That backstop is gone. **Per-call confirmation is now the only thing between a
# write and any project the signed-in person can reach.**
#
# WHAT IT DID NOT REMOVE. Every narrower rule still holds, everywhere, and none of
# them is configurable:
#
#   * no write of any kind without the user confirming THAT call
#   * contracts stay in draft — no tool accepts a status
#   * invoices may be submitted for review and never approved, rejected,
#     sent back or marked paid
#   * vendors cannot be created or changed at all
#   * integration fields are refused on every verb
#   * a record an ERP has locked is refused entirely
#
# To narrow it again, name projects explicitly:
#   FORMA_ALLOWED_CONTAINERS="<uuid>,<uuid>"   allow only those
#   FORMA_ALLOWED_CONTAINERS="*"               allow every project (the default now)
#
# The three Assemble projects this was built against, kept for reference and used
# throughout the tools and tests:
#   SANDBOX    Implementation Hub (CON1234) — fake, no real commitments
#   CLAYTON    CRC0209 — real records in production
#   FOOTSCRAY  WSF0017 — real records in production
_allowed_raw = os.environ.get("FORMA_ALLOWED_CONTAINERS", "*")
ALLOW_ALL_CONTAINERS = _allowed_raw.strip() == "*"
ALLOWED_CONTAINERS = (
    set()
    if ALLOW_ALL_CONTAINERS
    else {c.strip() for c in _allowed_raw.split(",") if c.strip()}
)

# --- HTTP ----------------------------------------------------------------------
HTTP_TIMEOUT = int(os.environ.get("FORMA_HTTP_TIMEOUT", "60"))
USER_AGENT = "Assemble-Forma-MCP/0.1 (+https://assemble.com.au)"


# --- The NetSuite integration --------------------------------------------------
# Assemble runs a Workato integration between Forma and NetSuite ("Assemble ACC
# NetSuite Integration"). It is NOT ours to touch, and the risk is not theoretical:
# measured on 15 Sep 2026, 24 of 100 Footscray expenses and 11 of 23 Clayton
# expenses carry externalSystem "NetSuite" with a real NetSuite externalId and a
# sync timestamp. Three Footscray expenses are integrationState "locked".
#
# Two distinct hazards, guarded separately:
#
# What must be protected is THE LINK, not the records that happen to use it:
#
#   PROTECTED   the integration's own fields (below), and deleting a synchronised
#               record — both change or break the link itself.
#   NORMAL WORK reading — status, comments, attachments, amounts, history — on a
#               synchronised record. 11 of Clayton's 23 expenses are linked, so
#               blocking that would block the main job.
#
# An earlier version refused every change to a linked record. That conflated the
# link with the data sitting on it, and would have made the plugin useless for
# expense approval — the thing it is most for.

# Fields the integration owns. Never send any of these in a request body.
INTEGRATION_OWNED_FIELDS = frozenset(
    {
        "externalId",
        "externalSystem",
        "externalMessage",
        "internalId",
        "internalSystem",
        "integrationState",
        "integrationStateChangedAt",
        "integrationStateChangedBy",
        "lastSyncTime",
        "bridgeInfo",
        "migrationStatus",
        "migrationUpdatedAt",
    }
)


# RECORDS THIS INTEGRATION MUST NEVER WRITE, WHATEVER ELSE IS PERMITTED.
#
# Not a safety margin — a description of where the data comes from. Both of these
# are OWNED BY NETSUITE, and Forma holds a downstream copy.
#
#   EXPENSES (invoices). They do not originate in Forma. Assemble's finance team
#   loads them into NetSuite, which pushes them here for the project team to
#   approve under the workflow configured in each project's cost settings; the
#   approval then travels back to NetSuite. Forma is the approval step in a
#   finance process, not the book of record. Writing an expense here — including
#   approving one — puts a machine inside a financial control that is meant to be
#   a named person clicking in Forma.
#
#   COMPANIES (vendors). NetSuite is the source of truth and pushes vendors into
#   ACC: 99 of the first 100 on Assemble's hub carry an `erpId`, i.e. NetSuite's
#   own identifier. A vendor created or edited here would be a local edit to
#   somebody else's master record — either silently overwritten on the next sync,
#   or worse, not.
#
# Reading both is entirely fine and is most of what this plugin is for: statuses,
# comments, attachments, amounts, who a vendor is, what they have billed.
READ_ONLY_PATH_FRAGMENTS = (
    "/expenses",          # /cost/v1/containers/:c/expenses[/...]
    "/companies",         # /construction/admin/v1/accounts/:a/companies, /hq/v1/...
)

# CREATING PROJECTS AND ADMINISTERING USERS — refused, on every verb.
#
# `account:write` was added on 16 Sep 2026 to reach project settings. It granted
# considerably more than that, as a probe demonstrated within a minute: a POST to
# the projects endpoint returned 202 and a real project appeared on the Assemble
# hub. ACC has no delete for projects; it could only be set inactive.
#
# The scope cannot be narrowed — Autodesk does not offer a finer one — so the
# capability is closed here instead. Nothing in either plugin needs to create a
# project or administer a user, and neither should be reachable by an accident of
# scope.
FORBIDDEN_PATH_FRAGMENTS = (
    "/users",             # project and account user administration
    "/business_units",
)


def creates_a_project(method: str, path: str) -> bool:
    """POST to a projects collection — i.e. making a new project."""
    if method.upper() != "POST":
        return False
    trimmed = path.split("?")[0].rstrip("/").lower()
    return trimmed.endswith("/projects")


# Cost object collections that carry integrationState, per Autodesk's own list:
# budget, contract, main contract, main contract item, cost item, expense,
# expense item, change order, schedule of value. These are the URL segments.
LOCKABLE_COLLECTIONS = frozenset(
    {
        "budgets",
        "contracts",
        "main-contracts",
        "main-contract-items",
        "cost-items",
        "sub-cost-items",
        "expenses",
        "change-orders",
        "schedule-of-values",
        "payments",
        "payment-items",
        "pco",
        "rfq",
        "rco",
        "oco",
        "sco",
        "cor",
    }
)


def integration_link(record: dict) -> dict | None:
    """Describe a record's integration link, or None if it has none.

    Read this before proposing any change to a record. A NetSuite-linked record
    looks exactly like any other until you check.
    """
    if not isinstance(record, dict):
        return None
    system = record.get("externalSystem")
    external_id = record.get("externalId")
    state = record.get("integrationState")
    if not (system or external_id or state):
        return None
    link = {
        "integrated_with": system or "unknown external system",
        "external_id": external_id,
        "integration_state": state,
        "last_synced": record.get("lastSyncTime"),
    }
    # A LOCKED RECORD IS A DIFFERENT SITUATION AND MUST NOT SHARE A NOTE WITH A
    # MERELY LINKED ONE.
    #
    # The single note this used to carry said approving, rejecting, revising and
    # commenting "are all fine" — true of a linked record, and false of a locked
    # one, where the write gate refuses all of them. It was therefore wrong in the
    # dangerous direction exactly where it mattered: it invited the model to
    # promise the user an action that would then be refused.
    #
    # Not hypothetical. On 16 Sep 2026 Clayton had five locked expenses, four of
    # them locked within the previous hour, while NetSuite worked through them.
    if state == "locked":
        link["status"] = "LOCKED — do not attempt to change this record"
        link["note"] = (
            f"{system or 'An external system'} is holding this record "
            "mid-synchronisation. Every change is refused while it stays locked — "
            "approving, rejecting, revising and commenting included — because "
            "altering it now can leave Forma and "
            f"{system or 'the other system'} disagreeing about the same record.\n\n"
            "Forma itself will NOT stop such a change; this plugin is the only "
            "thing that does. Tell the user the record is locked rather than "
            "offering to act on it. Locks usually clear within minutes. Do NOT "
            "offer to unlock it — clearing integrationState is what breaks the link."
        )
        if record.get("integrationStateChangedAt"):
            link["locked_since"] = record["integrationStateChangedAt"]
    else:
        link["note"] = (
            f"Synchronised with {system or 'an external system'} through Assemble's "
            "Workato integration, which is the source of truth for it. READ freely "
            "— status, comments, attachments, amounts, history. This plugin cannot "
            "change it: invoices arrive from NetSuite for approval and the approval "
            "travels back, so approving, rejecting and commenting are steps in a "
            "financial control and belong to a person in Forma. Report what you "
            "find and let them act."
        )
    return {k: v for k, v in link.items() if v is not None}
