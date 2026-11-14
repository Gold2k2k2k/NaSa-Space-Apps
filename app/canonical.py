"""Canonical JSON serialization used everywhere a result or receipt is hashed or compared.

Same data in, same text out: keys sorted, finite floats rounded to 6 decimals,
-0.0 normalized to 0.0, compact separators. No timestamps or unstable fields
may enter a verdict seal.
"""
import hashlib
import json
import math
from typing import Any

DECIMALS = 6


def _normalize(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite float cannot be serialized: {value!r}")
        rounded = round(value, DECIMALS)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"JSON keys must be strings, got {type(key).__name__}")
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    raise TypeError(f"Cannot serialize {type(value).__name__} to canonical JSON")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, payload: Any, length: int = 16) -> str:
    if type(length) is not int or not 1 <= length <= 64:
        raise ValueError("Identifier digest length must be between 1 and 64")
    return f"{prefix}-{sha256_of(payload)[:length]}"

