"""
Seed Licenses - API Views Package
---------------------------------
This package organizes all Django REST Framework views
under clear logical separation:
  - license_view.py → license operations
  - blockchain_view.py → blockchain & contract info
  - security_view.py → cryptographic key endpoints
"""

from .license_view import (
    submit_license_application,
    get_license_basic_info,
    get_license_action_history,
    get_license_qr_data,
    update_license_status_view,
    update_license_details,
    verify_license_document,
    check_total_license_count,
    add_officer_to_contract, 
)

from .blockchain_view import (
    check_owner_blockchain,
    contract_address_view,
    contract_methods_view,
    transaction_status_view,
    blockchain_health_check,
    blockchain_network_info,
    get_block_details, 
    view_all_cache_keys,
    clear_cache_view,
    redis_health_check
)

from .security_view import (
    get_public_key,
    security_health_check,
)

__all__ = [
    # License endpoints
    "submit_license_application",
    "get_license_basic_info",
    "get_license_action_history",
    "get_license_qr_data",
    "update_license_status_view",
    "update_license_details",
    "verify_license_document",
    "check_total_license_count",
    "add_officer_to_contract", 

    # Blockchain endpoints
    "check_owner_blockchain",
    "contract_address_view",
    "contract_methods_view",
    "transaction_status_view",
    "blockchain_health_check",
    "blockchain_network_info",
    "get_block_details", 

    # Security endpoints
    "get_public_key",
    "security_health_check",
    "view_all_cache_keys",
    "clear_cache_view",
    "redis_health_check"
]
