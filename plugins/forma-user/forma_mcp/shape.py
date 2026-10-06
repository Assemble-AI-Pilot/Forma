"""Turning Forma's data-shaped responses into answer-shaped ones.

Every byte crossing into the model should be a byte a human would want to read.
Forma makes that hard in a specific way: its records are extraordinarily WIDE.
Measured on a live project — budgets 212 fields, contracts 153, payments 113 —
and on a draft record almost all of them are null, zero, or an empty string.

Three levers, cheapest first:

  drop_empty   removes nulls, zeros and empty collections. Needs no knowledge of
               the object at all and typically removes 80-90% of a draft record.
  pick         keeps a named set of fields. Needs knowledge, gives the most
               control, and is what a purpose-built tool should use.
  money        renders Forma's "15000.000000000000" strings as numbers a human
               reads, and drops the ones that are zero.

Nothing here talks to the network.
"""
from __future__ import annotations

from typing import Any

# Fields that are pure plumbing: present on almost every record, meaningful to
# Autodesk's sync machinery, never the answer to anyone's question.
NOISE = frozenset(
    {
        "bridgeInfo",
        "changedBy",
        "containerId",
        "externalId",
        "externalMessage",
        "externalSystem",
        "integrationState",
        "integrationStateChangedAt",
        "integrationStateChangedBy",
        "internalId",
        "internalSystem",
        "lastSyncTime",
        "migrationStatus",
        "migrationUpdatedAt",
        "templateId",
        "aggregateBy",
        "forecastDistributionAt",
        "customBaseValues",
    }
)


def is_empty(value: Any) -> bool:
    """True for values that carry no information on a Forma record.

    Zero counts as empty here, which is a judgement call: on a 153-field contract
    the zeros are overwhelmingly "this financial dimension does not apply to this
    record", not "this is genuinely nil". Tools that need to assert a real zero
    should pick the field explicitly rather than rely on drop_empty.
    """
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return True
        # Forma renders money as a decimal string; "0.0000" is not information.
        try:
            return float(stripped) == 0.0
        except ValueError:
            return False
    if isinstance(value, bool):
        return value is False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


# Keys whose value is an ANSWER even when it is zero. drop_empty is correct on a
# record — a zero money field means "this dimension does not apply" — and wrong on
# a summary, where `matched: 0` IS the finding. Passing a summary through
# drop_empty made the count vanish exactly when it was zero, which is precisely
# when the user needs to be told "none".
ALWAYS_KEEP = frozenset(
    {"matched", "shown", "fetched", "count", "searched", "line_count", "total_rows",
     "checked", "mismatched", "verified", "all_fields_checked",
     # A False here is the whole answer: "this vendor is NOT usable on this
     # project yet". Dropped as empty, the field vanishes exactly when it carries
     # the finding — the same failure as a zero `matched` disappearing when the
     # answer is "none".
     "usable_on_this_project", "found_on_account"}
)


def drop_empty(record: Any, drop_noise: bool = True) -> Any:
    """Recursively remove empty values, and optionally the plumbing fields.

    The single highest-leverage transform available, because it needs no
    knowledge of the object: it is correct on an endpoint discovered five minutes
    ago just as much as on a well-understood one.
    """
    if isinstance(record, list):
        cleaned = [drop_empty(item, drop_noise) for item in record]
        return [item for item in cleaned if not is_empty(item)]
    if not isinstance(record, dict):
        return record
    out: dict[str, Any] = {}
    for key, value in record.items():
        if drop_noise and key in NOISE:
            continue
        cleaned = drop_empty(value, drop_noise)
        if key in ALWAYS_KEEP or not is_empty(cleaned):
            out[key] = cleaned
    return out


def dig(record: Any, dotted: str) -> Any:
    """Read a possibly-nested field by dotted path, through lists as well as dicts.

    An earlier version descended only into dicts, so any path crossing an array —
    `expenseItems.0.budgetId`, `budgetIds.0` — returned None, and forma_verify_write
    duly reported a perfectly good write as `silently_ignored`.

    It failed safe (a false alarm, not false reassurance) but it made ARRAYS
    unverifiable, and arrays are exactly what most needs verifying here: SOV lines,
    expense items and budgetIds are all arrays. A verifier that cries wolf on the
    structures you most need to check is one people learn to ignore, which is worse
    than having no verifier at all.

    Supported: `a.b`, `a.0.b` (index), and `a[].b` (every element, returned as a list).
    """
    current = record
    for part in dotted.split("."):
        if current is None:
            return None
        if part == "[]" or part == "*":
            if not isinstance(current, list):
                return None
            current = current  # the map happens on the next segment
            continue
        if isinstance(current, list):
            if part.isdigit():
                index = int(part)
                current = current[index] if -len(current) <= index < len(current) else None
            else:
                # A named segment against a list means "this field of every element".
                current = [
                    item.get(part) if isinstance(item, dict) else None for item in current
                ]
            continue
        if isinstance(current, dict):
            current = current.get(part)
            continue
        return None
    return current


def pick(record: Any, fields: list[str], keep_empty: bool = False) -> Any:
    """Keep only the named fields. Dotted paths collapse to their last segment."""
    if isinstance(record, list):
        return [pick(item, fields, keep_empty) for item in record]
    if not isinstance(record, dict):
        return record
    out: dict[str, Any] = {}
    for field in fields:
        value = dig(record, field)
        if keep_empty or not is_empty(value):
            out[field.split(".")[-1]] = value
    return out


def money(value: Any) -> float | None:
    """Forma returns money as a string like '15000.000000000000'. Make it a number.

    Returns None rather than 0.0 for an absent value, so a caller can tell "no
    figure" from "a figure of zero" — a distinction that matters when the question
    is "how much is left".
    """
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def aud(value: Any) -> str | None:
    """Render money the way it would be written in a sentence."""
    amount = money(value)
    if amount is None:
        return None
    return f"${amount:,.2f}"


def size_note(before: Any, after: Any) -> dict[str, Any]:
    """Report what shaping saved, so the saving is visible rather than assumed."""
    import json

    raw = len(json.dumps(before, default=str))
    shaped = len(json.dumps(after, default=str))
    note: dict[str, Any] = {
        "chars": f"{raw:,} -> {shaped:,}",
        "approx_tokens": f"{raw // 4:,} -> {shaped // 4:,}",
    }
    if shaped:
        note["reduction"] = f"{raw / shaped:.0f}x"
    return note


def rows_of(body: Any) -> list[dict[str, Any]]:
    """Get the records out of a Cost response, whatever envelope it arrived in.

    Most Cost endpoints return {"results": [...], "pagination": {...}}. Some —
    /change-orders and /properties — return a bare array with no envelope at all.
    A client that assumes one shape silently reads nothing from the other.
    """
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    if isinstance(body, dict):
        results = body.get("results")
        if isinstance(results, list):
            return [row for row in results if isinstance(row, dict)]
        return [body]
    return []


def total_of(body: Any, fallback_rows: list[Any] | None = None) -> int | None:
    """Total row count, from the pagination envelope where there is one."""
    if isinstance(body, dict):
        pagination = body.get("pagination")
        if isinstance(pagination, dict) and "totalResults" in pagination:
            return pagination["totalResults"]
    if isinstance(body, list):
        return len(body)
    return len(fallback_rows) if fallback_rows is not None else None
