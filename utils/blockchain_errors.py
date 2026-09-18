"""Normalize smart-contract revert errors for API clients."""

from __future__ import annotations

import re


class ContractRevertError(Exception):
    """Business-rule failure from a contract require()/revert (already cleaned)."""


_FALLBACK = "Request could not be completed. Please try again later."
_STRIP_CHARS = " '" + '"'


def clean_revert_message(exc: Exception, fallback: str = _FALLBACK) -> str:
    """
    Turn web3 noise into the solidity require() text.

    "Execution reverted (License must be active to generate QR data)"
      -> "License must be active to generate QR data"
    """
    try:
        raw = getattr(exc, "message", None) or str(exc)
        raw = str(raw).strip()

        tuple_msg = re.match(r"^\(\s*'([^']+)'\s*,", raw)
        if tuple_msg:
            raw = tuple_msg.group(1).strip()

        bracket = re.search(r"\(([^)]+)\)", raw)
        if bracket and re.search(r"(?i)execution\s+reverted", raw):
            reason = bracket.group(1).strip(_STRIP_CHARS)
            if reason:
                return reason

        colon = re.search(r"(?is)execution\s+reverted\s*:\s*(.+)$", raw)
        if colon:
            reason = colon.group(1).strip(_STRIP_CHARS)
            if reason:
                return reason

        if raw and "\n" not in raw and len(raw) < 200:
            if not re.search(r'(?i)execution\s+reverted|traceback|file "', raw):
                return raw

        return fallback
    except Exception:
        return fallback