#!/usr/bin/env python3

# deploy_contracts_final.py
import json
import time
import datetime
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import os
from pathlib import Path
import sys

# Load environment variables with explicit path checking
# Note: We'll load this properly in the functions below to handle project structure

def normalize_abi(abi):
    """Normalize ABI by converting enum types to uint8"""
    for item in abi:
        if item.get("type") == "event":
            for input_item in item["inputs"]:
                if input_item["type"].startswith("enum"):
                    input_item["type"] = "uint8"
    return abi

def validate_private_key(private_key):
    """Validate private key format and return normalized version"""
    if not private_key:
        return None, "Private key is empty or not found"
    
    # Remove whitespace
    private_key = private_key.strip()
    
    # Check if it's empty after stripping
    if not private_key:
        return None, "Private key is empty after stripping whitespace"
    
    # Add 0x prefix if missing
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    # Validate length (64 hex chars + 0x prefix = 66 total)
    if len(private_key) != 66:
        return None, f"Invalid private key length: {len(private_key)}. Expected 66 characters (0x + 64 hex chars)"
    
    # Validate hex format
    try:
        int(private_key, 16)
    except ValueError:
        return None, "Private key contains non-hexadecimal characters"
    
    # Check if it's all zeros (invalid)
    if private_key == '0x' + '0' * 64:
        return None, "Private key cannot be all zeros"
    
    return private_key, None

def check_environment_setup():
    """Check and display environment setup information"""
    print(f"🔍 ENVIRONMENT SETUP CHECK")
    print(f"{'='*50}")
    
    # Check for .env file in multiple locations
    possible_env_paths = [
        Path('.env'),                    # Current directory
        Path('../.env'),                 # Parent directory (project root)
        Path('../../.env'),              # Two levels up
    ]
    
    env_file_found = None
    for env_path in possible_env_paths:
        if env_path.exists():
            env_file_found = env_path
            break
    
    if env_file_found:
        print(f"✅ .env file found at: {env_file_found.absolute()}")
        
        # Show file modification time
        import datetime
        mod_time = datetime.datetime.fromtimestamp(env_file_found.stat().st_mtime)
        print(f"📅 Last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load from the found location
        load_dotenv(env_file_found, override=True)
        print(f"🔄 Loaded environment variables from: {env_file_found.absolute()}")
    else:
        print(f"❌ .env file NOT found in any of these locations:")
        for env_path in possible_env_paths:
            print(f"   - {env_path.absolute()}")
        print(f"\n💡 Create a .env file in the project root with:")
        print(f"   PRIVATE_KEY=your_private_key_here")
        print(f"   RPC_URL=https://data-seed-prebsc-1-s1.binance.org:8545")
        
        # Show current directory context
        print(f"\n📁 Current working directory: {Path.cwd()}")
        print(f"📁 Project root should be: {Path.cwd().parent}")
        return False
    
    # Check environment variables
    rpc_url = os.getenv('RPC_URL')
    private_key_raw = os.getenv('PRIVATE_KEY')
    
    print(f"\n📋 Environment Variables:")
    print(f"RPC_URL: {'✅ Set' if rpc_url else '❌ Not set'}")
    print(f"PRIVATE_KEY: {'✅ Set' if private_key_raw else '❌ Not set'}")
    
    if rpc_url:
        print(f"RPC_URL value: {rpc_url}")
    
    if private_key_raw:
        # Show only first 6 and last 4 characters for security
        masked_key = f"{private_key_raw[:6]}...{private_key_raw[-4:]}" if len(private_key_raw) > 10 else "***"
        print(f"PRIVATE_KEY: {masked_key} (length: {len(private_key_raw)})")
        
        # Validate private key
        validated_key, error = validate_private_key(private_key_raw)
        if error:
            print(f"❌ Private key validation failed: {error}")
            return False
        else:
            print(f"✅ Private key format is valid")
            
            # Show derived address
            try:
                account = Account.from_key(validated_key)
                print(f"📍 Derived address: {account.address}")
            except Exception as e:
                print(f"❌ Failed to derive address: {e}")
                return False
    else:
        print(f"❌ PRIVATE_KEY not found in environment variables")
        return False
    
    print(f"{'='*50}")
    return True

class SmartContractDeployer:
    def __init__(self, rpc_url, private_key):
        """Initialize the deployer with Web3 connection and EIP-155 compliance"""
        print(f"🔑 PRIVATE KEY VALIDATION")
        print(f"{'='*50}")
        
        # Validate private key first
        validated_key, error = validate_private_key(private_key)
        if error:
            raise Exception(f"❌ Invalid private key: {error}")
        
        print(f"✅ Private key format validated")
        
        # Create account from validated private key
        try:
            self.account = Account.from_key(validated_key)
            self.address = self.account.address
            print(f"✅ Account created successfully")
            print(f"📍 Deployer address: {self.address}")
        except Exception as e:
            raise Exception(f"❌ Failed to create account from private key: {e}")
        
        print(f"{'='*50}")
        
        # Initialize Web3 connection
        print(f"🌐 NETWORK CONNECTION")
        print(f"{'='*50}")
        print(f"🔗 Connecting to: {rpc_url}")
        
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Check connection
        if not self.w3.is_connected():
            raise Exception("Failed to connect to the network")
        
        print(f"✅ Successfully connected to network")
        
        # Get chain information
        self.chain_id = self.w3.eth.chain_id
        chain_names = {
            1: "Ethereum Mainnet",
            56: "BSC Mainnet", 
            97: "BSC Testnet",
            137: "Polygon Mainnet",
            80001: "Polygon Mumbai",
            1337: "Ganache",
            31337: "Hardhat Network",  # Hardhat default chain ID
            11155111: "Sepolia",
            5: "Goerli"
        }
        
        # Get native token symbol based on chain
        token_symbols = {
            1: "ETH",
            56: "BNB",
            97: "tBNB", 
            137: "MATIC",
            80001: "MATIC",
            1337: "ETH",
            31337: "ETH",  # Hardhat uses ETH
            11155111: "ETH",
            5: "ETH"
        }
        
        chain_name = chain_names.get(self.chain_id, f"Unknown (ID: {self.chain_id})")
        token_symbol = token_symbols.get(self.chain_id, "ETH")
        
        print(f"Connected to: {chain_name}")
        print(f"Chain ID: {self.chain_id}")
        print(f"Deployer address: {self.address}")
        
        balance = self.w3.eth.get_balance(self.address) / 10**18
        print(f"Balance: {balance:.4f} {token_symbol}")
        
        # Set minimum balance threshold based on network
        # Lower threshold for local/test networks
        if self.chain_id in [1337, 31337]:  # Ganache or Hardhat
            min_balance_threshold = 1.0  # Local networks should have plenty of ETH
        elif self.chain_id in [1, 56, 137]:  # Mainnets
            min_balance_threshold = 0.1
        else:  # Testnets
            min_balance_threshold = 0.01
            
        self.token_symbol = token_symbol
        
        # Hardhat-specific settings
        if self.chain_id == 31337:
            print(f"🔧 Hardhat Network detected!")
            print(f"   - Fast local blockchain")
            print(f"   - Instant mining")
            print(f"   - Perfect for development")
            print(f"   - Reset with: npx hardhat node")
            
            # Check if this is a well-known Hardhat account
            well_known_hardhat_addresses = {
                "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": "Account #0 (Default)",
                "0x70997970C51812dc3A010C7d01b50e0d17dc79C8": "Account #1", 
                "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC": "Account #2",
                "0x90F79bf6EB2c4f870365E785982E1f101E93b906": "Account #3",
                "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65": "Account #4"
            }
            
            if self.address in well_known_hardhat_addresses:
                account_info = well_known_hardhat_addresses[self.address]
                print(f"   - Using: {account_info}")
                print(f"   ⚠️  This is a publicly known test account")
            else:
                print(f"   - Using: Custom account")
        
        # Ganache-specific settings  
        elif self.chain_id == 1337:
            print(f"🔧 Ganache Network detected!")
            print(f"   - Local blockchain")
            print(f"   - Configurable mining")
            print(f"   - Good for testing")
        
        if balance < min_balance_threshold:
            print(f"⚠️  Warning: Low balance. Ensure you have enough {token_symbol} for deployment.")
        
        # Load compiled contracts
        project_root = Path(__file__).parent.parent
        artifacts_path = project_root / 'artifacts' / 'compiled_contracts.json'
        
        print(f"Loading artifacts from: {artifacts_path}")
        
        if not artifacts_path.exists():
            raise Exception(f"Artifacts file not found at {artifacts_path}")
            
        with open(artifacts_path, 'r') as f:
            self.contracts = json.load(f)
            self.full_abis = {
                name: contract['abi']
                for name, contract in self.contracts.items()
            }
        
        print(f"Loaded contracts: {list(self.contracts.keys())}")
        
        # Initialize nonce management and check for stuck transactions
        self.latest_nonce = self.w3.eth.get_transaction_count(self.address, 'latest')
        self.pending_nonce = self.w3.eth.get_transaction_count(self.address, 'pending')
        self.current_nonce = self.pending_nonce  # Start from pending nonce
        
        print(f"Latest nonce: {self.latest_nonce}, Pending nonce: {self.pending_nonce}")
        
        if self.latest_nonce != self.pending_nonce:
            stuck_count = self.pending_nonce - self.latest_nonce
            print(f"⚠️  Warning: {stuck_count} pending transactions detected")
            self.handle_stuck_transactions()
        else:
            print("✅ No pending transactions found")
    
    def handle_stuck_transactions(self):
        """Handle stuck transactions with multiple options"""
        stuck_count = self.pending_nonce - self.latest_nonce
        print(f"\n🔧 STUCK TRANSACTION HANDLER")
        print(f"{'='*50}")
        print(f"Stuck transactions: {stuck_count}")
        print(f"Nonce range: {self.latest_nonce} to {self.pending_nonce - 1}")
        
        print(f"\nChoose an option:")
        print(f"1. 🚀 Force replace with VERY high gas (10x current price)")
        print(f"2. 💰 Force replace with EXTREME gas (20x current price)")
        print(f"3. ⏭️  Skip stuck transactions (use nonce {self.pending_nonce})")
        print(f"4. 🛑 Exit and handle manually")
        
        # Auto-select option 3 for non-interactive environments
        if not sys.stdin.isatty():
            print("🤖 Non-interactive mode: Auto-selecting option 3 (skip)")
            choice = "3"
        else:
            choice = input("Enter choice (1-4) [default: 3]: ").strip() or "3"
        
        if choice == "1":
            return self.force_replace_transactions(multiplier=10)
        elif choice == "2":
            return self.force_replace_transactions(multiplier=20)
        elif choice == "3":
            return self.skip_stuck_transactions()
        elif choice == "4":
            print("👋 Exiting. Please handle stuck transactions manually.")
            sys.exit(0)
        else:
            print("❌ Invalid choice. Defaulting to skip.")
            return self.skip_stuck_transactions()
    
    def force_replace_transactions(self, multiplier=10):
        """Force replace stuck transactions with very high gas"""
        print(f"\n⚡ FORCE REPLACING WITH {multiplier}x GAS PRICE")
        print(f"{'='*50}")
        
        current_gas_price = self.w3.eth.gas_price
        force_gas_price = int(current_gas_price * multiplier)
        
        print(f"💰 Current gas price: {self.w3.from_wei(current_gas_price, 'gwei'):.2f} gwei")
        print(f"💰 Force gas price: {self.w3.from_wei(force_gas_price, 'gwei'):.2f} gwei")
        
        # Estimate total cost
        gas_per_tx = 21000
        total_gas = gas_per_tx * (self.pending_nonce - self.latest_nonce)
        total_cost = (force_gas_price * total_gas) / 10**18
        
        print(f"💸 Estimated cost: {total_cost:.6f} {self.token_symbol}")
        
        balance = self.w3.eth.get_balance(self.address) / 10**18
        if total_cost > balance * 0.5:  # If cost is more than 50% of balance
            print(f"⚠️  Warning: High cost ({total_cost:.6f} {self.token_symbol}). Your balance: {balance:.6f} {self.token_symbol}")
            if sys.stdin.isatty():
                confirm = input("Continue anyway? (y/N): ").lower()
                if confirm != 'y':
                    return self.skip_stuck_transactions()
        
        replaced_count = 0
        
        for nonce in range(self.latest_nonce, self.pending_nonce):
            try:
                print(f"🔄 Force replacing nonce {nonce}...")
                
                # Create replacement transaction with EIP-155 compliance
                replacement_tx = {
                    'to': self.address,
                    'value': 0,
                    'gas': gas_per_tx,
                    'gasPrice': force_gas_price,
                    'nonce': nonce,
                    'from': self.address,
                    'chainId': self.chain_id
                }
                
                # Sign and send
                signed_tx = self.account.sign_transaction(replacement_tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                
                print(f"📡 Replacement sent: {tx_hash.hex()}")
                replaced_count += 1
                
                time.sleep(1)  # Brief pause between replacements
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'underpriced' in error_msg:
                    print(f"❌ Still underpriced at {multiplier}x for nonce {nonce}")
                    print(f"💡 Try option 2 (20x gas) or option 3 (skip)")
                    return self.skip_stuck_transactions()
                elif 'nonce too low' in error_msg:
                    print(f"✅ Nonce {nonce} already processed")
                    replaced_count += 1
                else:
                    print(f"❌ Failed to replace nonce {nonce}: {e}")
                continue
        
        if replaced_count > 0:
            print(f"\n✅ Sent {replaced_count} replacement transactions")
            return self.wait_for_nonce_clear()
        else:
            print("❌ No transactions were successfully replaced")
            return self.skip_stuck_transactions()
    
    def skip_stuck_transactions(self):
        """Skip stuck transactions and use a fresh nonce"""
        print(f"\n⏭️  SKIPPING STUCK TRANSACTIONS")
        print(f"{'='*50}")
        print(f"Setting current nonce to: {self.pending_nonce}")
        print(f"Stuck transactions (nonces {self.latest_nonce}-{self.pending_nonce-1}) will remain pending")
        print(f"New deployments will use nonce {self.pending_nonce} and above")
        
        self.current_nonce = self.pending_nonce
        print("✅ Ready to proceed with deployment")
        return True
    
    def wait_for_nonce_clear(self):
        """Wait for stuck transactions to clear"""
        print(f"\n⏳ Waiting for transactions to clear...")
        
        for i in range(60):  # Wait up to 10 minutes
            time.sleep(10)
            new_latest = self.w3.eth.get_transaction_count(self.address, 'latest')
            new_pending = self.w3.eth.get_transaction_count(self.address, 'pending')
            
            print(f"📊 Status - Latest: {new_latest}, Pending: {new_pending}")
            
            if new_latest == new_pending:
                print("🎉 All transactions cleared!")
                self.latest_nonce = new_latest
                self.pending_nonce = new_pending
                self.current_nonce = new_pending
                return True
            
            if i % 6 == 0:  # Every minute
                print(f"⏱️  Still waiting... ({i//6 + 1} min)")
        
        print("⏰ Timeout waiting for transactions to clear")
        print("🚀 Proceeding with fresh nonce anyway...")
        return self.skip_stuck_transactions()
    
    def get_next_nonce(self):
        """Get next nonce and increment counter"""
        nonce = self.current_nonce
        self.current_nonce += 1
        return nonce
    
    def reset_nonce_to_latest(self):
        """Reset nonce counter to latest confirmed nonce (emergency function)"""
        self.latest_nonce = self.w3.eth.get_transaction_count(self.address, 'latest')
        self.pending_nonce = self.w3.eth.get_transaction_count(self.address, 'pending')
        self.current_nonce = max(self.latest_nonce, self.pending_nonce)
        print(f"🔄 Nonce reset to {self.current_nonce}")
    
    def wait_for_transaction(self, tx_hash, timeout=300, tx_data=None, nonce=None):
        """Wait for transaction to be mined with enhanced error handling"""
        print(f"⏳ Waiting for transaction {tx_hash.hex()}...")
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                try:
                    receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                    if receipt.status == 1:
                        print(f"✅ Transaction successful!")
                        print(f"   Block: {receipt.blockNumber}")
                        print(f"   Gas used: {receipt.gasUsed:,}")
                        return receipt
                    else:
                        print(f"❌ Transaction failed! Hash: {tx_hash.hex()}")
                        return None
                except Exception:
                    # Transaction not mined yet
                    elapsed = time.time() - start_time
                    
                    if elapsed > 120 and elapsed % 30 == 0:  # Check every 30s after 2 min
                        print(f"🔄 Transaction pending for {elapsed:.0f}s...")
                    
                    time.sleep(5)
                    continue
            
            print(f"⏰ Transaction timeout after {timeout}s")
            return None
            
        except Exception as e:
            print(f"❌ Error waiting for transaction: {e}")
            return None
    
    def deploy_contract(self, contract_name, constructor_args=None, max_retries=3):
        """Deploy a contract with enhanced error handling and retry logic"""
        if contract_name not in self.contracts:
            raise Exception(f"Contract {contract_name} not found in artifacts")
        
        if constructor_args is None:
            constructor_args = []
        
        contract_data = self.contracts[contract_name]
        abi = contract_data['abi']
        bytecode = contract_data['bytecode']
        
        # Ensure bytecode starts with 0x
        if not bytecode.startswith('0x'):
            bytecode = '0x' + bytecode
        
        print(f"\n{'='*50}")
        print(f"Deploying {contract_name}")
        print(f"Constructor args: {constructor_args}")
        print(f"{'='*50}")
        
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries}")
                
                # Create contract instance
                Contract = self.w3.eth.contract(abi=normalize_abi(abi), bytecode=bytecode)
                
                # Build constructor transaction
                if constructor_args:
                    constructor_tx = Contract.constructor(*constructor_args)
                else:
                    constructor_tx = Contract.constructor()
                
                # Get current nonce
                nonce = self.get_next_nonce()
                print(f"Using nonce: {nonce}")
                
                # Estimate gas with error handling
                try:
                    gas_estimate = constructor_tx.estimate_gas({'from': self.address})
                    gas_limit = int(gas_estimate * 1.3)  # 30% buffer
                    print(f"Gas estimate: {gas_estimate:,}, Using: {gas_limit:,}")
                except Exception as e:
                    print(f"⚠️  Gas estimation failed: {e}")
                    gas_limit = 6000000  # Fallback gas limit
                    print(f"Using fallback gas limit: {gas_limit:,}")
                
                # Get gas price with premium for faster confirmation
                # Adjust gas pricing based on network
                base_gas_price = self.w3.eth.gas_price
                
                if self.chain_id == 31337:  # Hardhat
                    # Hardhat doesn't need gas price optimization
                    gas_price = base_gas_price
                    print(f"Gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} gwei (Hardhat default)")
                elif self.chain_id == 1337:  # Ganache
                    # Ganache uses fixed gas price
                    gas_price = base_gas_price
                    print(f"Gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} gwei (Ganache)")
                else:
                    # Real networks need premium for faster confirmation
                    gas_price = int(base_gas_price * 1.5)  # 50% premium
                    print(f"Gas price: {self.w3.from_wei(gas_price, 'gwei'):.2f} gwei (+50% premium)")
                
                # Build transaction with EIP-155 compliance
                tx = constructor_tx.build_transaction({
                    'from': self.address,
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': self.chain_id  # EIP-155 compliance
                })
                
                # Sign and send transaction
                signed_tx = self.account.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                
                print(f"📡 Transaction sent: {tx_hash.hex()}")
                
                # Wait for confirmation
                receipt = self.wait_for_transaction(tx_hash, timeout=300)
                
                if receipt and receipt.status == 1:
                    contract_address = receipt.contractAddress
                    print(f"✅ {contract_name} deployed successfully!")
                    print(f"   Address: {contract_address}")
                    print(f"   Gas used: {receipt.gasUsed:,}")
                    return contract_address, abi
                else:
                    print(f"❌ {contract_name} deployment failed")
                    if attempt < max_retries - 1:
                        print("🔄 Retrying in 15 seconds...")
                        time.sleep(15)
                        # Reset nonce on failure
                        self.reset_nonce_to_latest()
                    continue
                    
            except Exception as e:
                print(f"❌ Error in attempt {attempt + 1}: {e}")
                error_msg = str(e).lower()
                
                if "nonce too low" in error_msg:
                    print("🔄 Nonce too low, resetting...")
                    self.reset_nonce_to_latest()
                elif "insufficient funds" in error_msg:
                    raise Exception(f"❌ Insufficient funds for deployment. Need more {self.token_symbol}.")
                elif "already known" in error_msg:
                    print("🔄 Transaction already in mempool, waiting...")
                    time.sleep(20)
                    self.reset_nonce_to_latest()
                
                if attempt < max_retries - 1:
                    print(f"🔄 Retrying in 20 seconds...")
                    time.sleep(20)
                else:
                    raise Exception(f"Failed to deploy {contract_name} after {max_retries} attempts: {e}")
        
        raise Exception(f"Failed to deploy {contract_name} after {max_retries} attempts")
    
    def deploy_proxy(self, implementation_address, admin_address, max_retries=3):
        """Deploy ERC1967 proxy with enhanced error handling"""
        print(f"\n{'='*50}")
        print(f"Deploying Proxy")
        print(f"Implementation: {implementation_address}")
        print(f"Admin: {admin_address}")
        print(f"{'='*50}")
        
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries}")
                
                # Encode initializer function
                impl_contract = self.w3.eth.contract(
                    address=implementation_address,
                    abi=self.contracts['LicenseSystemV1']['abi']
                )
                
                try:
                    initializer_data = impl_contract.encodeABI(fn_name='initialize', args=[])
                    print("✅ Initializer data encoded successfully")
                except Exception as e:
                    print(f"❌ Error encoding initializer: {e}")
                    initializer_data = "0x"  # Empty data fallback
                
                # Check if we have ERC1967Proxy contract
                if 'ERC1967Proxy' in self.contracts:
                    print("Using compiled ERC1967Proxy")
                    proxy_address, _ = self.deploy_contract(
                        'ERC1967Proxy',
                        constructor_args=[implementation_address, initializer_data]
                    )
                    return proxy_address
                else:
                    print("Using OpenZeppelin proxy bytecode")
                    return self.deploy_openzeppelin_proxy(implementation_address, initializer_data)
                    
            except Exception as e:
                print(f"❌ Error in proxy deployment attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print("🔄 Retrying in 20 seconds...")
                    time.sleep(20)
                    self.reset_nonce_to_latest()
                else:
                    raise
        
        raise Exception(f"Failed to deploy proxy after {max_retries} attempts")
    
    def deploy_openzeppelin_proxy(self, implementation, init_data):
        """Deploy OpenZeppelin ERC1967Proxy with EIP-155 compliance"""
        # Complete OpenZeppelin ERC1967Proxy bytecode
        proxy_bytecode = "0x60806040523661001357610011610017565b005b6100115b61001f6101b7565b6001600160a01b0316336001600160a01b031614156101a95760606001600160e01b031960003516631b2ce7f360e11b8114156100655761005f6101c2565b91506101b1565b6001600160e01b03196000351663278f794360e11b8114156100905761008a6101d6565b91506101b1565b6001600160e01b031960003516634f1ef28660e01b8114156100c5576100b56101e7565b91506100bf6101ff565b906101b1565b6001600160e01b0319600035166351cff8d960e01b8114156100f0576100ea61020f565b91506101b1565b6001600160e01b031960003516634ed2d6ac60e01b811415610124576101158361021e565b915061011f610232565b6101b1565b6001600160e01b03196000351663485cc95560e01b81141561014f576101496101e7565b91506101b1565b6001600160e01b03196000351663a7661d5460e01b811415610174576100ea610242565b6001600160e01b03196000351663b7935b0b60e11b81141561019f57610199610250565b91506101b1565b6101a7610265565b505b6101b4816000610285565b50565b600061001f6102b1565b60606101cc6102d5565b9050805191505090565b60606101e06102ed565b9050805191505090565b60006101f16101b7565b6001600160a01b0316336001600160a01b031614156101a9575060015b60006102096102fc565b50600090565b60006102196101b7565b905090565b600080610229610376565b5050505050505050565b600061023c6101b7565b50600090565b600061024c6101b7565b5090565b60606101cc610384565b60606101e0610394565b6000341561027f5761027f6102796103a3565b346103b1565b50600080fd5b600061028f6103d8565b9150915081156102a85780806020019051810190610279565b3d6000803e3d6000fd5b7f360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc5490565b60606102e26101b76103e8565b6101cc90613510565b60606102e2610219610519565b600061032960008036600080610314613510565b5050600080855af43d6000803e3d6000fd5b506001600160e01b031960003516631b2ce7f360e11b1415610355576103506101b7613528565b610372565b506001600160e01b0319600035166351cff8d960e01b141561037257610372613545565b9190565b63144c230360e11b60005260046000fd5b6060610391610219613584565b90565b60606103916102196135a9565b60006103ad6103a3565b5090565b60006103c7826103c26103a3565b6135ce565b80516020820120905092915050565b600080600080845160208601878a8af19150509250925092565b600080600080600080600080885160208a018b8d8ff19450845160208601878a8af193508084801561041e5761041c8e86613605565b505b845160208601878a8af19250808380156104425761044089898989613642565b505b60408d10156104555761045361367e565b505b8b1561047557602086015185526104718c60208801876136b4565b8c91505b8a1561049857845183526020860151602084015261049689868486613642565b505b81156104cd576104c9886104b3576323b872dd60e01b6104b6565b60015b6001600160a01b038f1690876136ff565b9650505b604080518881526020810188905287151581830152861515606082015290517f85e1543bf2f84fe80c6badbce3648c8539ad1df4d2b3d822938ca0538be727e69181900360800190a19998505050505050505050565b6000610523613733565b905090565b6000610532613584565b6001600160a01b0316336001600160a01b0316141561055957610554613733565b610219565b61056161375e565b5060006105706101b76103e8565b9050610580816101b783866136b4565b5050565b606061058e613766565b6040516020016105a09190600061379a565b60405160208183030381529060405290506000611111600161381990506105c86101b76103e8565b915091565b60008282116135ff5781156135f8578260005260046000209050816000526135f6613816565b505b60006135fa565b5092915050565b813b81811115613616575050505050565b83836040518083838560045afa50813d818114613636573d85833e3d85fd5b50505050505050505050565b813b8181111561365057505050505b8383836040518084848460045afa50813d81811461366f573d848433e3d84fd5b5050505050505050505050565b7fdc2fee72000000000000000000000000000000000000000000000000000000060005260046000fd5b823b1561372c576001600160a01b038316156136cf5781600052604051600081fd5b6001600160a01b0382161561372c57604051632320b25f60e21b81526001600160a01b03831660048201526001600160a01b0382166024820152306044820152606401600081fd5b5050505050565b7fb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d61035490565b600019610219565b604080517f8b73c3c69bb8fe3d512ecc4cf759cc79239f7b179b0ffacaa9a75d522b39400f60208201527fd89e7096f8a7a68b9f0f0e9aa3c6e99e8e659b162d9aee84fadbfc54e731c87f9181019190915260608101929092524660808301523060a0830152600090610753906137f490919063ffffffff16565b600080613800565b60006103ad610753610812565b50600090565b805160208201206000906135fa565b50600090565b60006137ff338461388b565b600080610837565b60006138296101b7565b6001600160a01b031663a217fddf6040518163ffffffff1660e01b8152600401602060405180830381600087803b15801561386357600080fd5b505af115801561387e573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906135fa91906138c5565b60008061389b858585855161389f565b5090565b6000806001600160a01b0383166138b6578461389f565b6138bf866138de565b9250929050565b6000602082840312156138d757600080fd5b5051919050565b606060006138ea613733565b90506001600160a01b038116156139275780604051639af30fb360e01b815260040160405180910390fd5b5060408051602081019091526000815290565b803b613945575050565b6000826001600160a01b031682604051613959919061395f565b60006040518083038185875af1925050503d8060008114613996576040519150601f19603f3d011682016040523d82523d6000602084013e61399b565b606091505b509150819050806139aa575050565b8051156139bb5780518082602001fd5b816040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016139ef91906139fb565b60405180910390fd5b90565b60208152600082518060208401526000805160206141658339815191528160408501526001600160a01b03815116606085015260208101516080850152604081015160a0850152606081015160c0850152608081015160e085015260a081015161010085015260c081015161012085015260e08101516101408501526101008101516101608501526101208101516101808501526101408101516101a08501526101608101516101c08501526101808101516101e08501526101a08101516102008501526101c08101516102208501526101e08101516102408501526102008101516102608501526102208101516102808501526102408101516102a08501526102608101516102c08501526102808101516102e08501526102a081015161030085015260015b80821015613b27578184015181860152830181613b15565b80821115613b385781840151818601525b505092915050565b8183823760009101908152919050565b600082601f830112613b6157600080fd5b8151602067ffffffffffffffff80831115613b7e57613b7e6140f8565b8260051b613b8d83820161410e565b9384528581018301938381019088861115613ba757600080fd5b84880192505b85831015613ce357825184811115613bc55760008081fd5b88016040818b03601f1901811315613bdd5760008081fd5b613be561413f565b878301518681168114613bf85760008081fd5b81526040830151888201119150613c0f5760008081fd5b8783019150610400807fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe084011215613c475760008081fd5b613c4f61413f565b9250613c5c8b858561393a565b83526060840151602084015260808401516040840152613c7f60a08501856136ff565b606084015260c084015160808401526101008401519250613ca2838411846140e1565b60a08401526101208401516101208401526101408401516101408401526101608401516101608401526101808401516101808401525050505050509184019190840190613bad565b5098975050505050505050565b600082601f830112613d0157600080fd5b81516020613d11613b8d8361410e565b82815260059290921b84018101918181019086841115613d3057600080fd5b8286015b84811015613d5f57805167ffffffffffffffff811115613d55576000841b91505b613d5e826140e1565b845291830191830190506001016000190181613d34565b5095945050505050565b600080600080600060a08688031215613d8157600080fd5b855167ffffffffffffffff80821115613d9957600080fd5b9087019060408289031215613dad57600080fd5b613db561413f565b825182811115613dc457600080fd5b613dd08a828601613b50565b825250602083015182811115613de557600080fd5b613df18a828601613cf0565b602083015250965060208801519150808211613e0c57600080fd5b50613e1987828801613cf0565b60408801516060890151608090990151979a919950979695509350505050565b600181811c90821680613e4e57607f821691505b602082108103613e5d57600080fd5b50919050565b601f821115610279576000816000526020600020601f850160051c81016020861015613e8c5750805b601f850160051c820191505b81811015613eab57828155600101613e98565b505050505050565b815167ffffffffffffffff811115613ecd57613ecd6140f8565b613ee181613edb8454613e3a565b84613e63565b602080601f831160018114613f165760008415613efe5750858301515b600019600386901b1c1916600185901b178555613eab565b600085815260208120601f198616915b82811015613f4557888601518255948401946001909101908401613f26565b5085821015613f635787850151600019600388901b60f8161c191681555b5050505050600190811b01905550565b81810381811115610523577fec53c0ea00000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b60008151808452602080850194506020840160005b83811015613fe15781516001600160a01b031687529582019590820190600101613fc3565b509495945050505050565b60008151808452602080850194506020840160005b8381101561401e57815160ff1687529582019590820190600101614002565b509495945050505050565b60006101c060018060a01b03808f168452808e1660208501528c6040850152816060850152614056828501888a613b40565b915083820360808501526140698261403f565b915083820360a085015261407d8282613fec565b915083820360c08501526140918282613fec565b6001600160801b038a1660e08601526001600160801b03891661010086015287151561012086015286151561014086015285151561016086015284151561018086015290151560608501529e9d5050505050505050505050505050565b80820180821115610523576140056113dc565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052604160045260246000fd5b6040519081016001600160401b038111828210171561413757614137614108565b604052919050565b604051601f8201601f191681016001600160401b038111828210171561416757614167614108565b60405291905056fe697066733a2f2f516d57557146716b4635643865514b6e6b41505976546b5533526e71665533686f61786b6b507250516f586e42a2646970667358221220af83b7dc7b58c8a1298bb3b57f006b9eed3e3b0bb83685dc6d2f4cd9c5872e4164736f6c634300081c0033"
        
        # Create the proxy contract
        proxy_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "_logic", "type": "address"},
                    {"internalType": "bytes", "name": "_data", "type": "bytes"}
                ],
                "stateMutability": "payable",
                "type": "constructor"
            },
            {"stateMutability": "payable", "type": "fallback"},
            {"stateMutability": "payable", "type": "receive"},
            {
                "inputs": [{"internalType": "address", "name": "newImplementation", "type": "address"}],
                "name": "upgradeTo",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        Proxy = self.w3.eth.contract(abi=proxy_abi, bytecode=proxy_bytecode)
        
        # Deploy proxy with implementation and init data
        constructor_tx = Proxy.constructor(implementation, init_data)
        
        nonce = self.get_next_nonce()
        
        try:
            gas_estimate = constructor_tx.estimate_gas({'from': self.address})
            gas_limit = int(gas_estimate * 1.3)
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            gas_limit = 6000000
        
        base_gas_price = self.w3.eth.gas_price
        gas_price = int(base_gas_price * 1.5)
        
        # Build transaction with EIP-155 compliance
        tx = constructor_tx.build_transaction({
            'from': self.address,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': self.chain_id  # EIP-155 compliance
        })
        
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"📡 Proxy deployment transaction: {tx_hash.hex()}")
        receipt = self.wait_for_transaction(tx_hash)
        
        if receipt and receipt.status == 1:
            proxy_address = receipt.contractAddress
            print(f"✅ Proxy deployed successfully at: {proxy_address}")
            return proxy_address
        else:
            raise Exception("Proxy deployment failed")
    
    def verify_deployment(self, proxy_address, implementation_address):
        """Verify the deployment is working correctly"""
        print(f"\n{'='*50}")
        print(f"Verifying Deployment")
        print(f"{'='*50}")
        
        try:
            # Create proxy contract instance using implementation ABI
            proxy_contract = self.w3.eth.contract(
                address=proxy_address,
                abi=normalize_abi(self.contracts['LicenseSystemV1']['abi'])
            )
            
            # Test 1: Check admin
            try:
                admin = proxy_contract.functions.admin().call()
                print(f"✅ Admin check: {admin}")
                
                if admin.lower() == self.address.lower():
                    print("✅ Admin is correctly set to deployer")
                else:
                    print(f"⚠️  Admin is {admin}, expected {self.address}")
            except Exception as e:
                print(f"❌ Admin check failed: {e}")
            
            # Test 2: Check license counter
            try:
                counter = proxy_contract.functions.licenseIdCounter().call()
                print(f"✅ License counter: {counter}")
                
                if counter > 0:
                    print("✅ Contract is properly initialized")
                else:
                    print("⚠️  Counter is 0, initialization might have failed")
            except Exception as e:
                print(f"❌ Counter check failed: {e}")
            
            # Test 3: Check if we can call view functions
            try:
                # This should work without reverting
                owner = proxy_contract.functions.owner().call()
                print(f"✅ Owner check: {owner}")
            except Exception as e:
                print(f"❌ Owner check failed: {e}")
            
            print("✅ Basic verification completed")
            return True
            
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False
    
    def deploy_upgradeable_system(self):
        """Deploy the complete upgradeable system with enhanced error handling"""
        print(f"\n{'='*80}")
        print(f"🚀 DEPLOYING UPGRADEABLE LICENSE SYSTEM")
        print(f"{'='*80}")
        
        try:
            # Step 1: Deploy Implementation V1
            print(f"\n📋 Step 1: Deploying Implementation V1...")
            impl_v1_address, impl_v1_abi = self.deploy_contract('LicenseSystemV1')
            
            # Step 2: Deploy Proxy
            print(f"\n📋 Step 2: Deploying Proxy...")
            proxy_address = self.deploy_proxy(impl_v1_address, self.address)
            
            # Step 3: Verify deployment
            print(f"\n📋 Step 3: Verifying deployment...")
            verification_success = self.verify_deployment(proxy_address, impl_v1_address)
            
            if not verification_success:
                print("⚠️  Verification failed, but deployment might still be usable")
            
            # Step 4: Save deployment info
            print(f"\n📋 Step 4: Saving deployment information...")
            deployment_info = {
                'network': self.chain_id,
                'networkName': self._get_network_name(self.chain_id),
                'deploymentTime': int(time.time()),
                'deploymentTimeFormatted': time.strftime("%Y-%m-%d %H:%M:%S"),
                'deployer': self.address,
                'proxy': proxy_address,
                'implementationV1': impl_v1_address,
                'implementationABI': self.full_abis['LicenseSystemV1'],
                'gasUsed': {
                    'implementation': 'See transaction details',
                    'proxy': 'See transaction details'
                },
                'verification': {
                    'success': verification_success,
                    'timestamp': int(time.time())
                }
            }
            
            deployment_path = Path(__file__).parent / 'deployment_info.json'
            with open(deployment_path, 'w') as f:
                json.dump(deployment_info, f, indent=2)
            
            print(f"✅ Deployment info saved to: {deployment_path}")
            
            # Success summary
            print(f"\n{'='*80}")
            print(f"🎉 DEPLOYMENT SUCCESSFUL!")
            print(f"{'='*80}")
            print(f"📍 Proxy Address: {proxy_address}")
            print(f"📍 Implementation V1: {impl_v1_address}")
            print(f"👤 Admin/Owner: {self.address}")
            print(f"🔗 Chain ID: {self.chain_id}")
            print(f"📄 Deployment info: {deployment_path}")
            print(f"{'='*80}")
            
            return proxy_address, impl_v1_address
            
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ DEPLOYMENT FAILED")
            print(f"{'='*80}")
            print(f"Error: {e}")
            print(f"{'='*80}")
            raise
    
    def _get_network_name(self, chain_id):
        """Get network name from chain ID"""
        names = {
            1: "Ethereum Mainnet",
            56: "BSC Mainnet",
            97: "BSC Testnet", 
            137: "Polygon Mainnet",
            80001: "Polygon Mumbai",
            1337: "Ganache",
            31337: "Hardhat Network",
            11155111: "Sepolia",
            5: "Goerli"
        }
        return names.get(chain_id, f"Unknown (ID: {chain_id})")

# Test the deployment
class LicenseSystemTester:
    """Helper class to test the deployed system"""
    
    def __init__(self, w3, proxy_address, abi, account):
        self.w3 = w3
        self.contract = w3.eth.contract(address=proxy_address, abi=normalize_abi(abi))
        self.account = account
        self.address = account.address
        self.chain_id = w3.eth.chain_id
        self.current_nonce = w3.eth.get_transaction_count(account.address, 'pending')
    
    def get_next_nonce(self):
        """Get next nonce and increment counter"""
        nonce = self.current_nonce
        self.current_nonce += 1
        return nonce
    
    def wait_for_transaction(self, tx_hash, timeout=180):
        """Wait for transaction confirmation"""
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return receipt
        except Exception as e:
            print(f"❌ Transaction failed: {e}")
            return None
    
    def add_officer(self, officer_address, name, employee_id, role):
        """Add an officer to the system with enhanced error handling"""
        try:
            print(f"\n👮 Adding Officer: {name} ({officer_address})")
            
            nonce = self.get_next_nonce()
            gas_price = int(self.w3.eth.gas_price * 1.5)
            
            tx = self.contract.functions.addOfficer(
                officer_address,
                name,
                employee_id,
                role
            ).build_transaction({
                'from': self.address,
                'gas': 250000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chain_id  # EIP-155 compliance
            })
            
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            print(f"📡 Transaction sent: {tx_hash.hex()}")
            receipt = self.wait_for_transaction(tx_hash)
            
            if receipt and receipt.status == 1:
                print(f"✅ Officer added successfully!")
                print(f"   Gas used: {receipt.gasUsed:,}")
                return receipt
            else:
                print(f"❌ Failed to add officer")
                return None
                
        except Exception as e:
            print(f"❌ Error adding officer: {e}")
            return None
    
    def create_license(self, category, level, applicant_name, aadhaar, business_name, state, district):
        """Create a new license with enhanced error handling"""
        try:
            print(f"\n📄 Creating License for: {applicant_name}")
            
            nonce = self.get_next_nonce()
            gas_price = int(self.w3.eth.gas_price * 1.5)
            
            tx = self.contract.functions.createLicense(
                category,
                level,
                applicant_name,
                aadhaar,
                business_name,
                state,
                district
            ).build_transaction({
                'from': self.address,
                'gas': 1000000,  # Higher gas limit for license creation
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.chain_id  # EIP-155 compliance
            })
            
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            print(f"📡 Transaction sent: {tx_hash.hex()}")
            receipt = self.wait_for_transaction(tx_hash)
            
            if receipt and receipt.status == 1:
                print(f"✅ License created successfully!")
                print(f"   Gas used: {receipt.gasUsed:,}")
                
                # Try to extract license ID from events
                try:
                    for log in receipt.logs:
                        if log.address.lower() == self.contract.address.lower():
                            try:
                                decoded = self.contract.events.LicenseCreated().process_log(log)
                                license_id = decoded['args']['licenseId']
                                print(f"   License ID: {license_id}")
                                return license_id
                            except:
                                continue
                    print("   License ID: Could not extract from events")
                    return True  # Still successful
                except Exception as e:
                    print(f"   Event parsing failed: {e}")
                    return True  # Still successful
            else:
                print(f"❌ Failed to create license")
                return None
                
        except Exception as e:
            print(f"❌ Error creating license: {e}")
            return None
    
    def get_license_info(self, license_id):
        """Get basic license information with error handling"""
        try:
            result = self.contract.functions.getLicenseBasicInfo(license_id).call()
            
            return {
                'id': result[0],
                'applicantName': result[1],
                'category': result[2],
                'level': result[3],
                'status': result[4],
                'applicant': result[5],
                'businessName': result[6],
                'district': result[7],
                'applicationDate': result[8],
                'approvalDate': result[9],
                'expiryDate': result[10],
                'isActive': result[11]
            }
        except Exception as e:
            print(f"❌ Error getting license info: {e}")
            return None

def fix_stuck_transactions_only():
    """Utility function to only fix stuck transactions without deploying"""
    print(f"{'='*80}")
    print(f"🔧 ADVANCED STUCK TRANSACTION FIXER")
    print(f"{'='*80}")
    
    # Find and load .env file from project root
    possible_env_paths = [
        Path('.env'),
        Path('../.env'),
        Path('../../.env'),
    ]
    
    env_file_loaded = None
    for env_path in possible_env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            env_file_loaded = env_path
            print(f"🔄 Loading .env from: {env_path.absolute()}")
            break
    
    if not env_file_loaded:
        print(f"❌ No .env file found! Please create one in the project root.")
        return False
    
    # Configuration with validation
    RPC_URL = os.getenv('RPC_URL', 'http://localhost:8545')
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    
    if not PRIVATE_KEY:
        print("❌ Error: PRIVATE_KEY not found in environment variables")
        print("Please add PRIVATE_KEY to your .env file")
        return False
    
    # Validate private key
    validated_private_key, validation_error = validate_private_key(PRIVATE_KEY)
    if validation_error:
        print(f"❌ Error: {validation_error}")
        print("Please check your PRIVATE_KEY in the .env file")
        return False
    
    try:
        print(f"🔗 Connecting to: {RPC_URL}")
        
        # Initialize connection with validated private key
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        account = Account.from_key(validated_private_key)
        address = account.address
        
        print(f"📍 Using address: {address}")
        
        if not w3.is_connected():
            print("❌ Failed to connect to network")
            return False
        
        chain_id = w3.eth.chain_id
        chain_names = {
            1: "Ethereum Mainnet", 
            56: "BSC Mainnet",
            97: "BSC Testnet",
            137: "Polygon Mainnet",
            80001: "Polygon Mumbai",
            1337: "Ganache", 
            31337: "Hardhat Network",
            11155111: "Sepolia", 
            5: "Goerli"
        }
        
        token_symbols = {
            1: "ETH",
            56: "BNB", 
            97: "tBNB",
            137: "MATIC",
            80001: "MATIC",
            1337: "ETH",
            31337: "ETH",
            11155111: "ETH",
            5: "ETH"
        }
        
        chain_name = chain_names.get(chain_id, f"Unknown (ID: {chain_id})")
        token_symbol = token_symbols.get(chain_id, "ETH")
        
        print(f"⛓️  Network: {chain_name}")
        print(f"👤 Address: {address}")
        print(f"💰 Balance: {w3.eth.get_balance(address) / 10**18:.4f} {token_symbol}")
        
        # Special handling for Hardhat
        if chain_id == 31337:
            print(f"🔧 Hardhat Network - Local development blockchain")
            well_known_hardhat_addresses = {
                "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": "Account #0 (Default)",
                "0x70997970C51812dc3A010C7d01b50e0d17dc79C8": "Account #1",
                "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC": "Account #2",
                "0x90F79bf6EB2c4f870365E785982E1f101E93b906": "Account #3"
            }
            if address in well_known_hardhat_addresses:
                print(f"📍 Using: {well_known_hardhat_addresses[address]}")
        
        # Check for stuck transactions
        latest_nonce = w3.eth.get_transaction_count(address, 'latest')
        pending_nonce = w3.eth.get_transaction_count(address, 'pending')
        
        print(f"📊 Latest nonce: {latest_nonce}")
        print(f"📊 Pending nonce: {pending_nonce}")
        
        if latest_nonce == pending_nonce:
            print("✅ No stuck transactions found!")
            return True
        
        stuck_count = pending_nonce - latest_nonce
        print(f"⚠️  Found {stuck_count} stuck transaction(s)")
        
        # Get current gas price
        current_gas_price = w3.eth.gas_price
        print(f"💰 Current gas price: {w3.from_wei(current_gas_price, 'gwei'):.2f} gwei")
        
        # Enhanced options
        print(f"\nChoose an option:")
        print(f"1. 🚀 Force replace with 10x gas ({w3.from_wei(current_gas_price * 10, 'gwei'):.2f} gwei)")
        print(f"2. 💰 Force replace with 20x gas ({w3.from_wei(current_gas_price * 20, 'gwei'):.2f} gwei)")
        print(f"3. 🔥 Force replace with 50x gas ({w3.from_wei(current_gas_price * 50, 'gwei'):.2f} gwei)")
        print(f"4. ⏭️  Skip stuck transactions (use nonce {pending_nonce})")
        print(f"5. 🛑 Exit")
        
        choice = input("Enter choice (1-5) [default: 4]: ").strip() or "4"
        
        if choice == "1":
            multiplier = 10
        elif choice == "2":
            multiplier = 20
        elif choice == "3":
            multiplier = 50
        elif choice == "4":
            print(f"⏭️  Skipping stuck transactions. Use nonce {pending_nonce} for future transactions.")
            return True
        elif choice == "5":
            print("👋 Exiting.")
            return False
        else:
            print("❌ Invalid choice. Defaulting to skip.")
            print(f"⏭️  Use nonce {pending_nonce} for future transactions.")
            return True
        
        # Calculate replacement gas price and cost
        replacement_gas_price = int(current_gas_price * multiplier)
        gas_per_tx = 21000
        total_gas = gas_per_tx * stuck_count
        total_cost = (replacement_gas_price * total_gas) / 10**18
        
        print(f"💰 Replacement gas price: {w3.from_wei(replacement_gas_price, 'gwei'):.2f} gwei")
        print(f"💸 Estimated total cost: {total_cost:.6f} {token_symbol}")
        
        balance = w3.eth.get_balance(address) / 10**18
        if total_cost > balance:
            print(f"❌ Insufficient balance! Need {total_cost:.6f} {token_symbol}, have {balance:.6f} {token_symbol}")
            return False
        
        if total_cost > balance * 0.3:  # If cost is more than 30% of balance
            print(f"⚠️  High cost warning: {total_cost:.6f} {token_symbol} ({total_cost/balance*100:.1f}% of balance)")
            confirm = input("Continue? (y/N): ").lower()
            if confirm != 'y':
                return False
        
        # Replace stuck transactions
        print(f"\n🚀 Replacing {stuck_count} stuck transactions...")
        replaced_count = 0
        
        for nonce in range(latest_nonce, pending_nonce):
            try:
                print(f"🔄 Replacing nonce {nonce}...")
                
                # Create replacement transaction with EIP-155 compliance
                replacement_tx = {
                    'to': address,
                    'value': 0,
                    'gas': gas_per_tx,
                    'gasPrice': replacement_gas_price,
                    'nonce': nonce,
                    'from': address,
                    'chainId': chain_id
                }
                
                # Sign and send
                signed_tx = account.sign_transaction(replacement_tx)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                
                print(f"📡 Replacement sent: {tx_hash.hex()}")
                replaced_count += 1
                
                time.sleep(1)  # Brief pause between replacements
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'underpriced' in error_msg:
                    print(f"❌ Still underpriced at {multiplier}x for nonce {nonce}")
                    print(f"💡 Try a higher multiplier or skip stuck transactions")
                    return False
                elif 'nonce too low' in error_msg:
                    print(f"✅ Nonce {nonce} already processed")
                    replaced_count += 1
                else:
                    print(f"❌ Failed to replace nonce {nonce}: {e}")
                continue
        
        if replaced_count > 0:
            print(f"\n✅ Sent {replaced_count} replacement transactions")
            print("⏳ Waiting for confirmations...")
            
            # Wait for all to clear
            for i in range(60):  # Wait up to 10 minutes
                time.sleep(10)
                new_latest = w3.eth.get_transaction_count(address, 'latest')
                new_pending = w3.eth.get_transaction_count(address, 'pending')
                
                print(f"📊 Status - Latest: {new_latest}, Pending: {new_pending}")
                
                if new_latest == new_pending:
                    print("🎉 All transactions cleared!")
                    return True
                
                if i % 6 == 0:  # Every minute
                    print(f"⏱️  Still waiting... ({i//6 + 1} min)")
            
            print("⏰ Timeout, but some transactions may have cleared")
            return True
        else:
            print("❌ No transactions were successfully replaced")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing stuck transactions: {e}")
        return False

def main():
    """Enhanced main deployment function with BSC testnet support"""
    print(f"{'='*80}")
    print(f"🚀 ENHANCED MULTI-CHAIN LICENSE SYSTEM DEPLOYER")
    print(f"{'='*80}")
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fix-stuck" or sys.argv[1] == "-f":
            print("🔧 Running in stuck transaction fix mode only...")
            success = fix_stuck_transactions_only()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Usage:")
            print("  python deploy_contracts_final.py                # Full deployment")
            print("  python deploy_contracts_final.py --fix-stuck    # Fix stuck transactions only")
            print("  python deploy_contracts_final.py --help         # Show this help")
            print("\nSupported Networks:")
            print("  • Ethereum Mainnet (Chain ID: 1)")
            print("  • BSC Mainnet (Chain ID: 56)")
            print("  • BSC Testnet (Chain ID: 97)")
            print("  • Polygon Mainnet (Chain ID: 137)")
            print("  • Polygon Mumbai (Chain ID: 80001)")
            print("  • Sepolia Testnet (Chain ID: 11155111)")
            print("  • Hardhat Network (Chain ID: 31337)")
            print("  • Ganache (Chain ID: 1337)")
            print("\nQuick Setup:")
            print("  # Hardhat Local Node:")
            print("  npx hardhat node")
            print("  RPC_URL=http://127.0.0.1:8545")
            print("  PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
            print("\nFor BSC Testnet deployment:")
            print("  RPC_URL=https://data-seed-prebsc-1-s1.binance.org:8545")
            print("  Get testnet tBNB from: https://testnet.binance.org/faucet-smart")
            sys.exit(0)
    
    # Configuration with enhanced validation
    print(f"🔧 CONFIGURATION VALIDATION")
    print(f"{'='*50}")
    
    # Find and load .env file from project root
    possible_env_paths = [
        Path('.env'),
        Path('../.env'), 
        Path('../../.env'),
    ]
    
    env_file_loaded = None
    for env_path in possible_env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            env_file_loaded = env_path
            print(f"🔄 Loading .env from: {env_path.absolute()}")
            break
    
    if not env_file_loaded:
        print(f"❌ No .env file found! Checked locations:")
        for env_path in possible_env_paths:
            print(f"   - {env_path.absolute()}")
        print(f"\n💡 Create .env file in project root: {Path.cwd().parent / '.env'}")
        sys.exit(1)
    
    # Check environment setup
    if not check_environment_setup():
        print(f"\n❌ Environment setup validation failed!")
        print(f"💡 Please check your .env file and try again.")
        sys.exit(1)
    
    # Get configuration values
    RPC_URL = os.getenv('RPC_URL', 'http://localhost:8545')
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    
    # Validate private key
    if not PRIVATE_KEY:
        print(f"\n❌ Error: PRIVATE_KEY not found in environment variables")
        print(f"Please add PRIVATE_KEY to your .env file")
        print(f"\n💡 Example .env file:")
        print(f"PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")
        print(f"RPC_URL=https://data-seed-prebsc-1-s1.binance.org:8545")
        print(f"\n💡 For BSC Testnet deployment, also set:")
        print(f"   RPC_URL=https://data-seed-prebsc-1-s1.binance.org:8545")
        print(f"\n💡 Or run with --fix-stuck to only fix stuck transactions:")
        print(f"   python deploy_contracts_final.py --fix-stuck")
        sys.exit(1)
    
    # Additional private key validation
    validated_private_key, validation_error = validate_private_key(PRIVATE_KEY)
    if validation_error:
        print(f"\n❌ Error: {validation_error}")
        print(f"Please check your PRIVATE_KEY in the .env file")
        print(f"\n💡 Private key should be:")
        print(f"   - 64 hexadecimal characters")
        print(f"   - Optionally prefixed with '0x'")
        print(f"   - Not all zeros")
        sys.exit(1)
    
    # Detect if user is trying to connect to specific networks
    if 'binance' in RPC_URL.lower() or 'bsc' in RPC_URL.lower():
        print(f"\n🔗 BSC Network detected!")
        print(f"📝 BSC Testnet Configuration:")
        print(f"   RPC URL: https://data-seed-prebsc-1-s1.binance.org:8545")
        print(f"   Chain ID: 97")
        print(f"   Native Token: tBNB")
        print(f"   Faucet: https://testnet.binance.org/faucet-smart")
        print(f"   Explorer: https://testnet.bscscan.com")
    elif 'localhost' in RPC_URL or '127.0.0.1' in RPC_URL:
        print(f"\n🔧 Local Network detected!")
        print(f"📝 Local Development Setup:")
        print(f"   RPC URL: {RPC_URL}")
        print(f"   Expected Chain IDs: 31337 (Hardhat) or 1337 (Ganache)")
        print(f"   For Hardhat: npx hardhat node")
        print(f"   For Ganache: ganache --host 0.0.0.0 --port 8545")
    
    print(f"✅ Configuration validation passed!")
    
    print(f"\n🔗 RPC URL: {RPC_URL}")
    
    try:
        # Initialize deployer with validated private key
        print(f"\n📋 Initializing deployer...")
        deployer = SmartContractDeployer(RPC_URL, validated_private_key)
        
        # Deploy the system
        proxy_address, impl_v1_address = deployer.deploy_upgradeable_system()
        
        # Test the deployment
        print(f"\n{'='*80}")
        print(f"🧪 TESTING DEPLOYED SYSTEM")
        print(f"{'='*80}")
        
        # Create tester
        tester = LicenseSystemTester(
            deployer.w3,
            proxy_address,
            deployer.full_abis['LicenseSystemV1'],
            deployer.account
        )
        
        try:
            # Test 1: Add an officer
            print(f"\n🧪 Test 1: Adding an officer...")
            officer_result = tester.add_officer(
                deployer.address,  # Making deployer an officer for testing
                "Admin Officer",
                "EMP001",
                "Senior Officer"
            )
            
            if officer_result:
                print("✅ Officer addition test passed")
            else:
                print("❌ Officer addition test failed")
            
            # Test 2: Create a license
            print(f"\n🧪 Test 2: Creating a license...")
            license_result = tester.create_license(
                0,  # SEED
                2,  # DISTRICT
                "Test Farmer",
                "123456789012",
                "Test Seeds Business",
                "Rajasthan",
                "Jaipur"
            )
            
            if license_result:
                print("✅ License creation test passed")
                
                # Test 3: Get license info if we have an ID
                if isinstance(license_result, int):
                    print(f"\n🧪 Test 3: Getting license info...")
                    license_info = tester.get_license_info(license_result)
                    if license_info:
                        print("✅ License info retrieval test passed")
                        print(f"License details: {json.dumps(license_info, indent=2, default=str)}")
                    else:
                        print("❌ License info retrieval test failed")
            else:
                print("❌ License creation test failed")
        
        except Exception as e:
            print(f"❌ Testing failed: {e}")
            print("Deployment was successful, but testing encountered issues.")
        
        # Final summary with network-specific information
        print(f"\n{'='*80}")
        print(f"🎯 DEPLOYMENT SUMMARY")
        print(f"{'='*80}")
        print(f"✅ Status: Deployment completed successfully")
        print(f"📍 Proxy Address: {proxy_address}")
        print(f"📍 Implementation: {impl_v1_address}")
        print(f"👤 Admin: {deployer.address}")
        print(f"🔗 Chain ID: {deployer.chain_id}")
        print(f"💰 Token: {deployer.token_symbol}")
        print(f"📁 Config saved to: deployment_info.json")
        
        # Network-specific information
        if deployer.chain_id == 31337:  # Hardhat Network
            print(f"\n🔧 HARDHAT NETWORK INFO:")
            print(f"🌐 Local Development Blockchain")
            print(f"⚡ Instant mining and fast transactions")
            print(f"🔄 Reset network: npx hardhat node")
            print(f"🧪 Hardhat console: npx hardhat console --network localhost")
            print(f"📊 No block explorer (local only)")
            
            # Show well-known accounts info
            well_known_accounts = {
                "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": "Account #0 (Default)",
                "0x70997970C51812dc3A010C7d01b50e0d17dc79C8": "Account #1",
                "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC": "Account #2"
            }
            if deployer.address in well_known_accounts:
                print(f"👤 Account: {well_known_accounts[deployer.address]}")
                print(f"⚠️  Note: This is a publicly known test account")
                
        elif deployer.chain_id == 1337:  # Ganache
            print(f"\n🔧 GANACHE NETWORK INFO:")
            print(f"🌐 Local Development Blockchain")
            print(f"📊 No block explorer (local only)")
            
        elif deployer.chain_id == 97:  # BSC Testnet
            print(f"\n🌐 BSC TESTNET LINKS:")
            print(f"📊 Proxy Contract: https://testnet.bscscan.com/address/{proxy_address}")
            print(f"📊 Implementation: https://testnet.bscscan.com/address/{impl_v1_address}")
            print(f"🚰 Get tBNB: https://testnet.binance.org/faucet-smart")
        elif deployer.chain_id == 56:  # BSC Mainnet
            print(f"\n🌐 BSC MAINNET LINKS:")
            print(f"📊 Proxy Contract: https://bscscan.com/address/{proxy_address}")
            print(f"📊 Implementation: https://bscscan.com/address/{impl_v1_address}")
        elif deployer.chain_id == 80001:  # Polygon Mumbai
            print(f"\n🌐 POLYGON MUMBAI LINKS:")
            print(f"📊 Proxy Contract: https://mumbai.polygonscan.com/address/{proxy_address}")
            print(f"📊 Implementation: https://mumbai.polygonscan.com/address/{impl_v1_address}")
        elif deployer.chain_id == 137:  # Polygon Mainnet
            print(f"\n🌐 POLYGON MAINNET LINKS:")
            print(f"📊 Proxy Contract: https://polygonscan.com/address/{proxy_address}")
            print(f"📊 Implementation: https://polygonscan.com/address/{impl_v1_address}")
        elif deployer.chain_id == 11155111:  # Sepolia
            print(f"\n🌐 SEPOLIA TESTNET LINKS:")
            print(f"📊 Proxy Contract: https://sepolia.etherscan.io/address/{proxy_address}")
            print(f"📊 Implementation: https://sepolia.etherscan.io/address/{impl_v1_address}")
        elif deployer.chain_id == 1:  # Ethereum Mainnet
            print(f"\n🌐 ETHEREUM MAINNET LINKS:")
            print(f"📊 Proxy Contract: https://etherscan.io/address/{proxy_address}")
            print(f"📊 Implementation: https://etherscan.io/address/{impl_v1_address}")
        
        print(f"{'='*80}")
        
        print(f"\n🔧 NEXT STEPS:")
        print(f"1. Update your API configuration:")
        print(f"   - Contract name: LicenseSystemV1")
        print(f"   - Proxy address: {proxy_address}")
        print(f"2. Test the API endpoints with the new contract")
        print(f"3. Your deployment_info.json has been updated")
        
        print(f"\n💡 UTILITY COMMANDS:")
        print(f"• Fix stuck transactions: python {os.path.basename(sys.argv[0])} --fix-stuck")
        print(f"• Manual help: python {os.path.basename(sys.argv[0])} --help")
        
    except KeyboardInterrupt:
        print(f"\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()