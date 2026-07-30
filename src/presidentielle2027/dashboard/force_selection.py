from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from urllib.parse import quote, unquote

COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365


def selection_from_cookie(
    cookies: Mapping[str, str],
    key: str,
    available: Sequence[str],
    default: Sequence[str],
) -> list[str]:
    available_list = list(dict.fromkeys(available))
    fallback = [value for value in default if value in available_list]
    raw = cookies.get(key)
    if not raw:
        return fallback
    try:
        payload = json.loads(unquote(raw))
        selected = set(payload.get("selected", []))
        known = set(payload.get("known", []))
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return fallback
    retained = [value for value in available_list if value in selected]
    new_values = [value for value in available_list if value not in known]
    return list(dict.fromkeys([*retained, *new_values]))


def selection_cookie_value(selected: Sequence[str], available: Sequence[str]) -> str:
    payload = {
        "selected": list(dict.fromkeys(selected)),
        "known": list(dict.fromkeys(available)),
    }
    return quote(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def cookie_javascript(key: str, value: str) -> str:
    safe_key = json.dumps(key)
    safe_value = json.dumps(value)
    return (
        "<script>"
        f"document.cookie={safe_key}+'='+{safe_value}+'; path=/; "
        f"max-age={COOKIE_MAX_AGE_SECONDS}; SameSite=Lax';"
        "</script>"
    )
