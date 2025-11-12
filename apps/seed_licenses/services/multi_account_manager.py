import logging
import random
from typing import List, Dict, Optional
from django.conf import settings
from web3 import Web3

logger = logging.getLogger(__name__)


class MultiAccountManager:
    """
    Manages multiple accounts from environment variables for load balancing.
    Falls back to single account mode for backward compatibility.
    """
    
    def __init__(self):
        self.accounts: List[Dict] = []
        self._load_accounts()
    
    def _load_accounts(self):
        """Load accounts from environment variables."""
        # Method 1: Multiple accounts from PRIVATE_KEYS and CONTRACT_ADDRESSES
        if hasattr(settings, 'PRIVATE_KEYS') and hasattr(settings, 'CONTRACT_ADDRESSES'):
            if settings.PRIVATE_KEYS and settings.CONTRACT_ADDRESSES:
                min_count = min(len(settings.PRIVATE_KEYS), len(settings.CONTRACT_ADDRESSES))
                
                for i in range(min_count):
                    try:
                        private_key = settings.PRIVATE_KEYS[i]
                        address = settings.CONTRACT_ADDRESSES[i]
                        
                        # Validate the private key matches the address
                        derived_address = Web3().eth.account.from_key(private_key).address
                        if derived_address.lower() != Web3.to_checksum_address(address).lower():
                            logger.warning(f"⚠️ Private key {i+1} doesn't match address {address}")
                            continue
                            
                        self.accounts.append({
                            "address": Web3.to_checksum_address(address),
                            "private_key": private_key,
                            "source": "env_multi",
                            "index": i
                        })
                        logger.info(f"✅ Loaded account {i+1}: {address}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to load account {i+1}: {e}")
        
        # Method 2: Single account from PRIVATE_KEY and CONTRACT_ADDRESS (backward compatibility)
        if hasattr(settings, 'PRIVATE_KEY') and settings.PRIVATE_KEY and hasattr(settings, 'CONTRACT_ADDRESS') and settings.CONTRACT_ADDRESS:
            try:
                # Validate that PRIVATE_KEY matches CONTRACT_ADDRESS
                derived_address = Web3().eth.account.from_key(settings.PRIVATE_KEY).address
                if derived_address.lower() == Web3.to_checksum_address(settings.CONTRACT_ADDRESS).lower():
                    # Check if this account is already loaded from multi-accounts
                    existing_account = self.get_account_by_address(settings.CONTRACT_ADDRESS)
                    if not existing_account:
                        self.accounts.append({
                            "address": Web3.to_checksum_address(settings.CONTRACT_ADDRESS),
                            "private_key": settings.PRIVATE_KEY,
                            "source": "env_single",
                            "index": len(self.accounts)
                        })
                        logger.info(f"✅ Loaded single account: {settings.CONTRACT_ADDRESS}")
                else:
                    logger.warning(f"⚠️ PRIVATE_KEY doesn't match CONTRACT_ADDRESS")
                    
            except Exception as e:
                logger.error(f"❌ Failed to load single account: {e}")
        
        if not self.accounts:
            logger.warning("⚠️ No accounts loaded from environment variables")
        else:
            logger.info(f"✅ Total accounts loaded: {len(self.accounts)}")
    
    def get_random_account(self) -> Optional[Dict]:
        """Get a random account for load balancing."""
        if not self.accounts:
            return None
        return random.choice(self.accounts)
    
    def get_account_by_index(self, index: int) -> Optional[Dict]:
        """Get specific account by index."""
        if 0 <= index < len(self.accounts):
            return self.accounts[index]
        return None
    
    def get_account_by_address(self, address: str) -> Optional[Dict]:
        """Get specific account by address."""
        checksum_address = Web3.to_checksum_address(address)
        for account in self.accounts:
            if account["address"].lower() == checksum_address.lower():
                return account
        return None
    
    def get_account_count(self) -> int:
        """Get total number of available accounts."""
        return len(self.accounts)
    
    def get_accounts_info(self) -> List[Dict]:
        """Get information about all loaded accounts."""
        return [
            {
                "address": acc["address"],
                "source": acc["source"],
                "index": acc["index"]
            }
            for acc in self.accounts
        ]


# Singleton instance
multi_account_manager = MultiAccountManager()