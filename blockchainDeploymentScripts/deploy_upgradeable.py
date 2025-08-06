#!/usr/bin/env python3

import json
import time
import os
import sys
from pathlib import Path
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Constants
NETWORK_METADATA = {
    1: {"name": "Ethereum Mainnet", "symbol": "ETH"},
    56: {"name": "BSC Mainnet", "symbol": "BNB"},
    97: {"name": "BSC Testnet", "symbol": "tBNB"},
    137: {"name": "Polygon Mainnet", "symbol": "MATIC"},
    80001: {"name": "Polygon Mumbai", "symbol": "MATIC"},
    1337: {"name": "Ganache", "symbol": "ETH"},
    31337: {"name": "Hardhat Network", "symbol": "ETH"},
    11155111: {"name": "Sepolia", "symbol": "ETH"},
    5: {"name": "Goerli", "symbol": "ETH"}
}

HARDHAT_ACCOUNTS = {
    "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": "Account #0 (Default)",
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8": "Account #1",
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC": "Account #2",
    "0x90F79bf6EB2c4f870365E785982E1f101E93b906": "Account #3",
    "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65": "Account #4"
}

# Utility Functions
def normalize_abi(abi):
    """Convert enum types to uint8 in ABI for compatibility"""
    for item in abi:
        if item.get("type") == "event":
            for input_item in item["inputs"]:
                if input_item["type"].startswith("enum"):
                    input_item["type"] = "uint8"
    return abi

def validate_private_key(private_key):
    """Validate and normalize private key format"""
    if not private_key:
        return None, "Private key is empty"
    
    private_key = private_key.strip()
    if not private_key:
        return None, "Private key is empty after stripping"
    
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    if len(private_key) != 66:
        return None, f"Invalid private key length: {len(private_key)}. Expected 66 characters"
    
    try:
        int(private_key, 16)
    except ValueError:
        return None, "Private key contains non-hexadecimal characters"
    
    if private_key == '0x' + '0' * 64:
        return None, "Private key cannot be all zeros"
    
    return private_key, None

def load_environment():
    """Load environment variables from .env file"""
    env_paths = [Path('.'), Path('..'), Path('../..')]
    for path in env_paths:
        env_file = path / '.env'
        if env_file.exists():
            load_dotenv(env_file, override=True)
            return env_file
    return None

def get_network_metadata(chain_id):
    """Get network name and token symbol from chain ID"""
    return NETWORK_METADATA.get(chain_id, {
        "name": f"Unknown (ID: {chain_id})",
        "symbol": "ETH"
    })

def mask_private_key(private_key):
    """Mask private key for secure display"""
    if len(private_key) < 10:
        return "***"
    return f"{private_key[:6]}...{private_key[-4:]}"

def handle_stuck_transactions_menu():
    """Display menu for stuck transaction options"""
    print("\nSTUCK TRANSACTION HANDLER")
    print("="*50)
    print("1. Force replace with VERY high gas (10x current price)")
    print("2. Force replace with EXTREME gas (20x current price)")
    print("3. Skip stuck transactions")
    print("4. Exit and handle manually")
    
    if not sys.stdin.isatty():
        print("Non-interactive mode: Auto-selecting option 3 (skip)")
        return "3"
    return input("Enter choice (1-4) [default: 3]: ").strip() or "3"

class SmartContractDeployer:
    def __init__(self, rpc_url, private_key):
        """Initialize deployer with Web3 connection"""
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.account = Account.from_key(private_key)
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to network")
        
        self.chain_id = self.w3.eth.chain_id
        self.network_meta = get_network_metadata(self.chain_id)
        self.address = self.account.address
        self.balance = self.w3.eth.get_balance(self.address)
        self.token_symbol = self.network_meta["symbol"]
        
        self._load_contracts()
        self._init_nonce_management()
        self._log_network_info()

    def _load_contracts(self):
        """Load compiled contract artifacts"""
        artifacts_path = Path(__file__).parent.parent / 'artifacts' / 'compiled_contracts.json'
        if not artifacts_path.exists():
            raise FileNotFoundError(f"Artifacts file not found at {artifacts_path}")
            
        with open(artifacts_path, 'r') as f:
            contracts = json.load(f)
            self.contracts = contracts
            self.full_abis = {name: contract['abi'] for name, contract in contracts.items()}
        
        print(f"Loaded contracts: {', '.join(self.contracts.keys())}")

    def _init_nonce_management(self):
        """Initialize nonce counters and check for stuck transactions"""
        self.latest_nonce = self.w3.eth.get_transaction_count(self.address, 'latest')
        self.pending_nonce = self.w3.eth.get_transaction_count(self.address, 'pending')
        self.current_nonce = self.pending_nonce
        
        print(f"Nonce - Latest: {self.latest_nonce}, Pending: {self.pending_nonce}")
        
        if self.latest_nonce != self.pending_nonce:
            stuck_count = self.pending_nonce - self.latest_nonce
            print(f"Warning: {stuck_count} pending transactions detected")
            self._handle_stuck_transactions()

    def _log_network_info(self):
        """Log detailed network information"""
        print(f"\nNETWORK INFORMATION")
        print("="*50)
        print(f"Connected to: {self.network_meta['name']}")
        print(f"Chain ID: {self.chain_id}")
        print(f"Deployer address: {self.address}")
        print(f"Balance: {self.balance / 10**18:.4f} {self.token_symbol}")
        
        if self.chain_id == 31337 and self.address in HARDHAT_ACCOUNTS:
            print(f"{HARDHAT_ACCOUNTS[self.address]} (Hardhat Network)")

    def _handle_stuck_transactions(self):
        """Handle stuck transactions with user interaction"""
        choice = handle_stuck_transactions_menu()
        if choice == "1":
            self._force_replace_transactions(10)
        elif choice == "2":
            self._force_replace_transactions(20)
        elif choice == "3":
            self._skip_stuck_transactions()
        elif choice == "4":
            print("Exiting. Handle stuck transactions manually.")
            sys.exit(0)

    def _force_replace_transactions(self, multiplier):
        """Replace stuck transactions with higher gas price"""
        base_gas_price = self.w3.eth.gas_price
        force_gas_price = int(base_gas_price * multiplier)
        stuck_count = self.pending_nonce - self.latest_nonce
        
        print(f"\n⚡ FORCE REPLACING WITH {multiplier}x GAS")
        print("="*50)
        print(f"Current gas: {self.w3.from_wei(base_gas_price, 'gwei'):.2f} gwei")
        print(f"Forced gas: {self.w3.from_wei(force_gas_price, 'gwei'):.2f} gwei")
        
        # Estimate cost
        gas_per_tx = 21000
        total_cost = (force_gas_price * gas_per_tx * stuck_count) / 10**18
        balance_eth = self.balance / 10**18
        print(f"Estimated cost: {total_cost:.6f} {self.token_symbol}")
        print(f"Current balance: {balance_eth:.6f} {self.token_symbol}")
        
        if total_cost > balance_eth * 0.5 and sys.stdin.isatty():
            confirm = input("Continue? (y/N): ").lower()
            if confirm != 'y':
                return self._skip_stuck_transactions()
        
        for nonce in range(self.latest_nonce, self.pending_nonce):
            try:
                tx = {
                    'to': self.address,
                    'value': 0,
                    'gas': gas_per_tx,
                    'gasPrice': force_gas_price,
                    'nonce': nonce,
                    'chainId': self.chain_id
                }
                signed_tx = self.account.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"Replacement sent for nonce {nonce}: {tx_hash.hex()}")
                time.sleep(1)
            except Exception as e:
                error_msg = str(e).lower()
                if 'underpriced' in error_msg:
                    print(f"Still underpriced at {multiplier}x for nonce {nonce}")
                    return self._skip_stuck_transactions()
                elif 'nonce too low' in error_msg:
                    print(f"Nonce {nonce} already processed")
                else:
                    print(f"Failed to replace nonce {nonce}: {e}")
        
        self._wait_for_nonce_clear()

    def _skip_stuck_transactions(self):
        """Skip stuck transactions and use fresh nonce"""
        print(f"\nSKIPPING STUCK TRANSACTIONS")
        print("="*50)
        print(f"Setting current nonce to: {self.pending_nonce}")
        self.current_nonce = self.pending_nonce

    def _wait_for_nonce_clear(self):
        """Wait for pending transactions to clear"""
        print("\nWaiting for transactions to clear...")
        for _ in range(60):
            time.sleep(10)
            latest = self.w3.eth.get_transaction_count(self.address, 'latest')
            pending = self.w3.eth.get_transaction_count(self.address, 'pending')
            
            if latest == pending:
                print("All transactions cleared!")
                self.latest_nonce = self.pending_nonce = latest
                self.current_nonce = latest
                return
        print("Timeout waiting for transactions to clear")
        self._skip_stuck_transactions()

    def get_next_nonce(self):
        """Get next nonce and increment counter"""
        nonce = self.current_nonce
        self.current_nonce += 1
        return nonce

    def deploy_contract(self, contract_name, constructor_args=None, max_retries=3):
        """Deploy contract with error handling and retry logic"""
        contract_data = self.contracts.get(contract_name)
        if not contract_data:
            raise ValueError(f"Contract {contract_name} not found in artifacts")
        
        constructor_args = constructor_args or []
        abi = normalize_abi(contract_data['abi'])
        bytecode = contract_data['bytecode']
        if not bytecode.startswith('0x'):
            bytecode = '0x' + bytecode
        
        print(f"\nDEPLOYING {contract_name}")
        print("="*50)
        print(f"Constructor args: {constructor_args}")
        
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        constructor = contract.constructor(*constructor_args) if constructor_args else contract.constructor()
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"\nAttempt {attempt}/{max_retries}")
                nonce = self.get_next_nonce()
                
                # Gas estimation
                try:
                    gas_estimate = constructor.estimate_gas({'from': self.address})
                    gas_limit = int(gas_estimate * 1.3)
                except Exception:
                    gas_limit = 6000000
                
                # Gas pricing
                base_gas_price = self.w3.eth.gas_price
                gas_price = base_gas_price if self.chain_id in [1337, 31337] else int(base_gas_price * 1.5)
                
                # Build transaction
                tx = constructor.build_transaction({
                    'from': self.address,
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': self.chain_id
                })
                
                # Sign and send
                signed_tx = self.account.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"Transaction sent: {tx_hash.hex()}")
                
                # Wait for receipt
                receipt = self._wait_for_transaction(tx_hash)
                if receipt and receipt.status == 1:
                    print(f"{contract_name} deployed at: {receipt.contractAddress}")
                    return receipt.contractAddress, abi
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'nonce too low' in error_msg or 'already known' in error_msg:
                    self._reset_nonce_to_latest()
                if attempt < max_retries:
                    print(f"Retrying in 15 seconds...")
                    time.sleep(15)
                else:
                    raise RuntimeError(f"Deployment failed after {max_retries} attempts: {e}")

    def _wait_for_transaction(self, tx_hash, timeout=300):
        """Wait for transaction confirmation"""
        print(f"Waiting for transaction {tx_hash.hex()}...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt.status == 1:
                    print(f"Transaction successful! Block: {receipt.blockNumber}")
                    return receipt
                print(f"Transaction failed! Hash: {tx_hash.hex()}")
                return None
            except Exception:
                time.sleep(5)
        
        print(f"Transaction timeout after {timeout}s")
        return None

    def deploy_proxy(self, implementation_address):
        """Deploy ERC1967 proxy for upgradeable contract"""
        print(f"\nDEPLOYING PROXY")
        print("="*50)
        print(f"Implementation: {implementation_address}")
        
        # Encode initializer
        impl_contract = self.w3.eth.contract(
            address=implementation_address,
            abi=self.contracts['LicenseSystemV1']['abi']
        )
        
        try:
            initializer_data = impl_contract.functions.initialize()._encode_transaction_data()
        except Exception:
            initializer_data = b''
        
        return self.deploy_contract(
            'ERC1967Proxy',
            constructor_args=[implementation_address, initializer_data]
        )[0]

    def deploy_upgradeable_system(self):
        """Deploy complete upgradeable system with V1, V2 and proxy"""
        print("\n" + "="*80)
        print("DEPLOYING UPGRADEABLE LICENSE SYSTEM")
        print("="*80)
        
        try:
            # Deploy implementations
            print("\nStep 1: Deploying Implementations")
            impl_v1 = self.deploy_contract('LicenseSystemV1')[0]
            impl_v2 = self.deploy_contract('LicenseSystemV2')[0]
            
            # Deploy proxy
            print("\nStep 2: Deploying Proxy")
            proxy = self.deploy_proxy(impl_v1)
            
            # Verify deployment
            print("\nStep 3: Verifying Deployment")
            self._verify_deployment(proxy, impl_v1)
            
            # Upgrade to V2
            print("\nStep 4: Upgrading to V2")
            self._upgrade_proxy(proxy, impl_v2)
            
            # Save deployment info
            print("\nStep 5: Saving Deployment Info")
            self._save_deployment_info(proxy, impl_v1, impl_v2)
            
            print("\n" + "="*80)
            print("DEPLOYMENT SUCCESSFUL!")
            print("="*80)
            print(f"Proxy Address: {proxy}")
            print(f"Implementation V1: {impl_v1}")
            print(f"Implementation V2: {impl_v2}")
            print("="*80)
            
            return proxy, impl_v1, impl_v2
            
        except Exception as e:
            print("\n" + "="*80)
            print("DEPLOYMENT FAILED")
            print("="*80)
            print(f"Error: {e}")
            raise

    def _verify_deployment(self, proxy_address, implementation_address):
        """Verify proxy deployment"""
        try:
            proxy_contract = self.w3.eth.contract(
                address=proxy_address,
                abi=normalize_abi(self.contracts['LicenseSystemV1']['abi'])
            )
            owner = proxy_contract.functions.owner().call()
            print(f"Contract owner: {owner}")
            print("Basic verification completed")
        except Exception as e:
            print(f"Verification failed: {e}")

    def _upgrade_proxy(self, proxy_address, new_implementation):
        """Upgrade proxy to new implementation"""
        proxy_contract = self.w3.eth.contract(
            address=proxy_address,
            abi=self.full_abis['LicenseSystemV1']
        )
        
        nonce = self.get_next_nonce()
        empty_data = b''
        upgrade_tx = proxy_contract.functions.upgradeToAndCall(new_implementation, empty_data)
        
        try:
            gas_estimate = upgrade_tx.estimate_gas({'from': self.address})
            gas_limit = int(gas_estimate * 1.3)
        except Exception:
            gas_limit = 200000
        
        gas_price = self.w3.eth.gas_price
        tx = upgrade_tx.build_transaction({
            'from': self.address,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': self.chain_id
        })
        
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Upgrade transaction sent: {tx_hash.hex()}")
        self._wait_for_transaction(tx_hash)

    def _save_deployment_info(self, proxy, impl_v1, impl_v2):
        """Save deployment details to JSON file"""
        deployment_info = {
            'network': self.chain_id,
            'networkName': self.network_meta["name"],
            'deploymentTime': int(time.time()),
            'deploymentTimeFormatted': time.strftime("%Y-%m-%d %H:%M:%S"),
            'deployer': self.address,
            'proxy': proxy,
            'currentImplementation': 'V2',
            'admin': self.address,
            'implementations': {
                'V1': {'address': impl_v1, 'abi': self.full_abis['LicenseSystemV1']},
                'V2': {'address': impl_v2, 'abi': self.full_abis['LicenseSystemV2']}
            }
        }
        
        deployment_path = Path(__file__).parent / 'deployment_info.json'
        with open(deployment_path, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"Deployment info saved to: {deployment_path}")

def fix_stuck_transactions(rpc_url, private_key):
    """Utility to fix stuck transactions without deploying"""
    print("\n" + "="*80)
    print("🔧 STUCK TRANSACTION FIXER")
    print("="*80)
    
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print("Failed to connect to network")
        return False
    
    account = Account.from_key(private_key)
    address = account.address
    chain_id = w3.eth.chain_id
    network_meta = get_network_metadata(chain_id)
    token_symbol = network_meta["symbol"]
    
    print(f"Network: {network_meta['name']}")
    print(f"Address: {address}")
    print(f"Balance: {w3.eth.get_balance(address) / 10**18:.4f} {token_symbol}")
    
    # Check for stuck transactions
    latest_nonce = w3.eth.get_transaction_count(address, 'latest')
    pending_nonce = w3.eth.get_transaction_count(address, 'pending')
    
    if latest_nonce == pending_nonce:
        print("No stuck transactions found")
        return True
    
    stuck_count = pending_nonce - latest_nonce
    print(f"Found {stuck_count} stuck transaction(s)")
    
    # Enhanced options
    print("\nChoose an option:")
    print("1. Force replace with 10x gas")
    print("2. Force replace with 20x gas")
    print("3. Force replace with 50x gas")
    print("4. Skip stuck transactions")
    print("5. Exit")
    
    choice = input("Enter choice (1-5) [default: 4]: ").strip() or "4"
    multiplier = {"1": 10, "2": 20, "3": 50}.get(choice)
    
    if not multiplier:
        print(f"Skipping stuck transactions")
        return True
    
    # Calculate cost
    base_gas_price = w3.eth.gas_price
    replacement_gas_price = int(base_gas_price * multiplier)
    gas_per_tx = 21000
    total_cost = (replacement_gas_price * gas_per_tx * stuck_count) / 10**18
    balance = w3.eth.get_balance(address) / 10**18
    
    print(f"Estimated cost: {total_cost:.6f} {token_symbol}")
    print(f"Current balance: {balance:.6f} {token_symbol}")
    
    if total_cost > balance:
        print("Insufficient funds")
        return False
    
    # Replace transactions
    for nonce in range(latest_nonce, pending_nonce):
        try:
            tx = {
                'to': address,
                'value': 0,
                'gas': gas_per_tx,
                'gasPrice': replacement_gas_price,
                'nonce': nonce,
                'chainId': chain_id
            }
            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"📡 Replacement sent for nonce {nonce}: {tx_hash.hex()}")
            time.sleep(1)
        except Exception as e:
            print(f"Failed to replace nonce {nonce}: {e}")
    
    return True

def main():
    """Main deployment function with CLI options"""
    print("\n" + "="*80)
    print("SMART CONTRACT DEPLOYMENT MANAGER")
    print("="*80)
    
    # Handle CLI arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--fix-stuck", "-f"]:
            print("🔧 Running in stuck transaction fix mode")
            env_file = load_environment()
            if not env_file:
                print(".env file not found")
                return
            
            rpc_url = os.getenv('RPC_URL')
            private_key = os.getenv('PRIVATE_KEY')
            if not private_key:
                print("PRIVATE_KEY not found in .env")
                return
                
            validated_key, error = validate_private_key(private_key)
            if error:
                print(f"Invalid private key: {error}")
                return
                
            success = fix_stuck_transactions(rpc_url, validated_key)
            sys.exit(0 if success else 1)
            
        elif sys.argv[1] in ["--help", "-h"]:
            print("Usage:")
            print("  python deploy.py                # Full deployment")
            print("  python deploy.py --fix-stuck    # Fix stuck transactions")
            return
    
    # Load environment
    env_file = load_environment()
    if not env_file:
        print(".env file not found")
        return
    
    rpc_url = os.getenv('RPC_URL')
    private_key = os.getenv('PRIVATE_KEY')
    
    if not rpc_url or not private_key:
        print("Missing RPC_URL or PRIVATE_KEY in .env")
        return
    
    # Validate private key
    validated_key, error = validate_private_key(private_key)
    if error:
        print(f"Invalid private key: {error}")
        return
    
    # Initialize and deploy
    try:
        deployer = SmartContractDeployer(rpc_url, validated_key)
        deployer.deploy_upgradeable_system()
    except Exception as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()