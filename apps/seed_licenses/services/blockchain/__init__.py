"""
Blockchain Service Layer for Seed License System
------------------------------------------------
This package provides a clean, modular, and SOLID-compliant abstraction
over blockchain interactions (Besu QBFT).

Public Interfaces:
- TransactionService  → read/write operations on smart contracts
- EventParser         → event decoding and persistence
- format_and_transform_response → contract result transformer
- get_contract        → contract loader (cached ABI + proxy)
- w3                  → configured Web3 instance
"""

from .connection import w3, get_default_account
from .contract_manager import get_contract
from .transaction_service import TransactionService
from .event_parser import EventParser
from .data_transformer import format_and_transform_response, format_unix_timestamp

__all__ = [
    "w3",
    "get_default_account",
    "get_contract",
    "TransactionService",
    "EventParser",
    "format_and_transform_response",
    "format_unix_timestamp",
]
