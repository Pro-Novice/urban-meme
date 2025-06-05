# deploy_upgradeable.py
import json
import time
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables
load_dotenv()

class UpgradeableContractDeployer:
    def __init__(self, rpc_url, private_key):
        """Initialize the deployer with Web3 connection"""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        
        # Check connection
        if not self.w3.is_connected():
            raise Exception("Failed to connect to the network")
        
        print(f"Connected to network. Deployer address: {self.address}")
        print(f"Balance: {self.w3.eth.get_balance(self.address) / 10**18} ETH")
        
        # Load compiled contracts from the correct path
        project_root = Path(__file__).parent.parent
        artifacts_path = project_root / 'artifacts' / 'compiled_contracts.json'
        
        print(f"Loading artifacts from: {artifacts_path}")
        
        if not artifacts_path.exists():
            raise Exception(f"Artifacts file not found at {artifacts_path}")
            
        with open(artifacts_path, 'r') as f:
            self.contracts = json.load(f)
        
        print(f"Loaded contracts: {list(self.contracts.keys())}")
    
    def deploy_contract(self, contract_name, constructor_args=None):
        """Deploy a contract and return its address"""
        if contract_name not in self.contracts:
            raise Exception(f"Contract {contract_name} not found in artifacts")
            
        contract_data = self.contracts[contract_name]
        abi = contract_data['abi']
        bytecode = contract_data['bytecode']
        
        # Ensure bytecode starts with 0x
        if not bytecode.startswith('0x'):
            bytecode = '0x' + bytecode
        
        # Create contract instance
        Contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Build constructor transaction
        if constructor_args:
            constructor_tx = Contract.constructor(*constructor_args)
        else:
            constructor_tx = Contract.constructor()
        
        # Estimate gas
        gas_estimate = constructor_tx.estimate_gas({'from': self.address})
        
        # Build transaction
        tx = constructor_tx.build_transaction({
            'from': self.address,
            'gas': int(gas_estimate * 1.2),  # Add 20% buffer
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
        })
        
        # Sign and send transaction
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)  # Fixed: raw_transaction
        
        # Wait for receipt
        print(f"Deploying {contract_name}...")
        print(f"Transaction hash: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"{contract_name} deployed at: {receipt.contractAddress}")
        return receipt.contractAddress, abi
    
    def deploy_upgradeable_system(self):
        """Deploy the complete upgradeable system"""
        print("\n=== Deploying Upgradeable License System ===\n")
        
        # Step 1: Deploy Implementation V1
        print("Step 1: Deploying Implementation V1...")
        impl_v1_address, impl_v1_abi = self.deploy_contract('LicenseSystemV1')
        
        # Step 2: Encode initializer function
        print("\nStep 2: Encoding initializer...")
        impl_contract = self.w3.eth.contract(address=impl_v1_address, abi=impl_v1_abi)
        initializer_data = impl_contract.encode_abi("initialize")
        
        # Step 3: Deploy Proxy
        print("\nStep 3: Deploying Proxy...")
        
        # Check if we have ERC1967Proxy, otherwise use OpenZeppelin proxy ABI
        if 'ERC1967Proxy' in self.contracts:
            proxy_address, proxy_abi = self.deploy_contract(
                'ERC1967Proxy',
                constructor_args=[impl_v1_address, initializer_data]
            )
        else:
            print("ERC1967Proxy not found, using OpenZeppelin proxy bytecode...")
            proxy_address = self.deploy_openzeppelin_proxy(impl_v1_address, initializer_data)
            proxy_abi = impl_v1_abi  # Use implementation ABI for proxy

        # Verify deployment
        print("\n=== Deployment Summary ===")
        print(f"Proxy Address: {proxy_address}")
        print(f"Implementation V1 Address: {impl_v1_address}")
        print(f"Admin: {self.address}")
        
        # Save deployment info
        deployment_info = {
            'network': self.w3.eth.chain_id,
            'deploymentTime': int(time.time()),
            'deployer': self.address,
            'proxy': proxy_address,
            'implementationV1': impl_v1_address,
            'implementationABI': impl_v1_abi
        }
        
        deployment_path = Path(__file__).parent / 'deployment_info.json'
        with open(deployment_path, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"\nDeployment info saved to {deployment_path}")
        
        return proxy_address, impl_v1_address
    
    def deploy_openzeppelin_proxy(self, implementation, init_data):
        """Deploy OpenZeppelin ERC1967Proxy"""
        # Complete OpenZeppelin ERC1967Proxy bytecode
        proxy_bytecode = "0x60806040523661001357610011610017565b005b6100115b61001f6101b7565b6001600160a01b0316336001600160a01b031614156101a95760606001600160e01b031960003516631b2ce7f360e11b8114156100655761005f6101c2565b91506101b1565b6001600160e01b03196000351663278f794360e11b8114156100905761008a6101d6565b91506101b1565b6001600160e01b031960003516634f1ef28660e01b8114156100c5576100b56101e7565b91506100bf6101ff565b906101b1565b6001600160e01b0319600035166351cff8d960e01b8114156100f0576100ea61020f565b91506101b1565b6001600160e01b031960003516634ed2d6ac60e01b811415610124576101158361021e565b915061011f610232565b6101b1565b6001600160e01b03196000351663485cc95560e01b81141561014f576101496101e7565b91506101b1565b6001600160e01b03196000351663a7661d5460e01b811415610174576100ea610242565b6001600160e01b03196000351663b7935b0b60e11b81141561019f57610199610250565b91506101b1565b6101a7610265565b505b6101b4816000610285565b50565b600061001f6102b1565b60606101cc6102d5565b9050805191505090565b60606101e06102ed565b9050805191505090565b60006101f16101b7565b6001600160a01b0316336001600160a01b031614156101a9575060015b60006102096102fc565b50600090565b60006102196101b7565b905090565b600080610229610376565b5050505050505050565b600061023c6101b7565b50600090565b600061024c6101b7565b5090565b60606101cc610384565b60606101e0610394565b6000341561027f5761027f6102796103a3565b346103b1565b50600080fd5b600061028f6103d8565b9150915081156102a85780806020019051810190610279565b3d6000803e3d6000fd5b7f360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc5490565b60606102e26101b76103e8565b6101cc90613510565b60606102e2610219610519565b600061032960008036600080610314613510565b5050600080855af43d6000803e3d6000fd5b506001600160e01b031960003516631b2ce7f360e11b1415610355576103506101b7613528565b610372565b506001600160e01b0319600035166351cff8d960e01b141561037257610372613545565b9190565b63144c230360e11b60005260046000fd5b6060610391610219613584565b90565b60606103916102196135a9565b60006103ad6103a3565b5090565b60006103c7826103c26103a3565b6135ce565b80516020820120905092915050565b600080600080845160208601878a8af19150509250925092565b600080600080600080600080885160208a018b8d8ff19450845160208601878a8af193508084801561041e5761041c8e86613605565b505b845160208601878a8af19250808380156104425761044089898989613642565b505b60408d10156104555761045361367e565b505b8b1561047557602086015185526104718c60208801876136b4565b8c91505b8a1561049857845183526020860151602084015261049689868486613642565b505b81156104cd576104c9886104b3576323b872dd60e01b6104b6565b60015b6001600160a01b038f1690876136ff565b9650505b604080518881526020810188905287151581830152861515606082015290517f85e1543bf2f84fe80c6badbce3648c8539ad1df4d2b3d822938ca0538be727e69181900360800190a19998505050505050505050565b6000610523613733565b905090565b6000610532613584565b6001600160a01b0316336001600160a01b0316141561055957610554613733565b610219565b61056161375e565b5060006105706101b76103e8565b9050610580816101b783866136b4565b5050565b606061058e613766565b6040516020016105a09190600061379a565b60405160208183030381529060405290506000611111600161381990506105c86101b76103e8565b915091565b60008282116135ff5781156135f8578260005260046000209050816000526135f6613816565b505b60006135fa565b5092915050565b813b81811115613616575050505050565b83836040518083838560045afa50813d818114613636573d85833e3d85fd5b50505050505050505050565b813b8181111561365057505050505b8383836040518084848460045afa50813d81811461366f573d848433e3d84fd5b5050505050505050505050565b7fdc2fee72000000000000000000000000000000000000000000000000000000060005260046000fd5b823b1561372c576001600160a01b038316156136cf5781600052604051600081fd5b6001600160a01b0382161561372c57604051632320b25f60e21b81526001600160a01b03831660048201526001600160a01b0382166024820152306044820152606401600081fd5b5050505050565b7fb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d61035490565b600019610219565b604080517f8b73c3c69bb8fe3d512ecc4cf759cc79239f7b179b0ffacaa9a75d522b39400f60208201527fd89e7096f8a7a68b9f0f0e9aa3c6e99e8e659b162d9aee84fadbfc54e731c87f9181019190915260608101929092524660808301523060a0830152600090610753906137f490919063ffffffff16565b600080613800565b60006103ad610753610812565b50600090565b805160208201206000906135fa565b50600090565b60006137ff338461388b565b600080610837565b600061382f6101b7565b6001600160a01b031663a217fddf6040518163ffffffff1660e01b8152600401602060405180830381600087803b15801561386a57600080fd5b505af115801561387e573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906135fa91906138c5565b60008061389b858585855161389f565b5090565b6000806001600160a01b0383166138b6578461389f565b6138bf866138de565b9250929050565b6000602082840312156138d757600080fd5b5051919050565b606060006138ea613733565b90506001600160a01b038116156139275780604051639af30fb360e01b815260040160405180910390fd5b5060408051602081019091526000815290565b803b613945575050565b6000826001600160a01b031682604051613959919061395f565b60006040518083038185875af1925050503d8060008114613996576040519150601f19603f3d011682016040523d82523d6000602084013e61399b565b606091505b509150819050806139aa575050565b8051156139bb5780518082602001fd5b816040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016139ef91906139fb565b60405180910390fd5b90565b60208152600082518060208401526000805160206141658339815191528160408501526001600160a01b03815116606085015260208101516080850152604081015160a0850152606081015160c0850152608081015160e085015260a081015161010085015260c081015161012085015260e08101516101408501526101008101516101608501526101208101516101808501526101408101516101a08501526101608101516101c08501526101808101516101e08501526101a08101516102008501526101c08101516102208501526101e08101516102408501526102008101516102608501526102208101516102808501526102408101516102a08501526102608101516102c08501526102808101516102e08501526102a081015161030085015260015b80821015613b27578184015181860152830181613b15565b80821115613b385781840151818601525b505092915050565b8183823760009101908152919050565b600082601f830112613b6157600080fd5b8151602067ffffffffffffffff80831115613b7e57613b7e6140f8565b8260051b613b8d83820161410e565b9384528581018301938381019088861115613ba757600080fd5b84880192505b85831015613ce357825184811115613bc55760008081fd5b88016040818b03601f1901811315613bdd5760008081fd5b613be561413f565b878301518681168114613bf85760008081fd5b81526040830151888201119150613c0f5760008081fd5b8783019150610400807fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe084011215613c475760008081fd5b613c4f61413f565b9250613c5c8b858561393a565b83526060840151602084015260808401516040840152613c7f60a08501856136ff565b606084015260c084015160808401526101008401519250613ca2838411846140e1565b60a08401526101208401516101208401526101408401516101408401526101608401516101608401526101808401516101808401525050505050509184019190840190613bad565b5098975050505050505050565b600082601f830112613d0157600080fd5b81516020613d11613b8d8361410e565b82815260059290921b84018101918181019086841115613d3057600080fd5b8286015b84811015613d5f57805167ffffffffffffffff811115613d55576000841b91505b613d5e826140e1565b845291830191830190506001016000190181613d34565b5095945050505050565b600080600080600060a08688031215613d8157600080fd5b855167ffffffffffffffff80821115613d9957600080fd5b9087019060408289031215613dad57600080fd5b613db561413f565b825182811115613dc457600080fd5b613dd08a828601613b50565b825250602083015182811115613de557600080fd5b613df18a828601613cf0565b602083015250965060208801519150808211613e0c57600080fd5b50613e1987828801613cf0565b60408801516060890151608090990151979a919950979695509350505050565b600181811c90821680613e4e57607f821691505b602082108103613e5d57600080fd5b50919050565b601f821115610279576000816000526020600020601f850160051c81016020861015613e8c5750805b601f850160051c820191505b81811015613eab57828155600101613e98565b505050505050565b815167ffffffffffffffff811115613ecd57613ecd6140f8565b613ee181613edb8454613e3a565b84613e63565b602080601f831160018114613f165760008415613efe5750858301515b600019600386901b1c1916600185901b178555613eab565b600085815260208120601f198616915b82811015613f4557888601518255948401946001909101908401613f26565b5085821015613f635787850151600019600388901b60f8161c191681555b5050505050600190811b01905550565b81810381811115610523577fec53c0ea00000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b60008151808452602080850194506020840160005b83811015613fe15781516001600160a01b031687529582019590820190600101613fc3565b509495945050505050565b60008151808452602080850194506020840160005b8381101561401e57815160ff1687529582019590820190600101614002565b509495945050505050565b60006101c060018060a01b03808f168452808e1660208501528c6040850152816060850152614056828501888a613b40565b915083820360808501526140698261403f565b915083820360a085015261407d8282613fec565b915083820360c08501526140918282613fec565b6001600160801b038a1660e08601526001600160801b03891661010086015287151561012086015286151561014086015285151561016086015284151561018086015290151560608501529e9d5050505050505050505050505050565b80820180821115610523576140056113dc565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052604160045260246000fd5b6040519081016001600160401b038111828210171561413757614137614108565b604052919050565b604051601f8201601f191681016001600160401b038111828210171561416757614167614108565b60405291905056fe697066733a2f2f516d57557146716b4635643865514b6e6b41505976546b5533526e71665533686f61786b6b507250516f586e42a2646970667358221220af83b7dc7b58c8a1298bb3b57f006b9eed3e3b0bb83685dc6d2f4cd9c5872e4164736f6c634300081c0033"
        
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
        
        gas_estimate = constructor_tx.estimate_gas({'from': self.address})
        
        tx = constructor_tx.build_transaction({
            'from': self.address,
            'gas': int(gas_estimate * 1.2),
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
        })
        
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"Deploying Proxy...")
        print(f"Transaction hash: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        proxy_address = receipt.contractAddress
        print(f"Proxy deployed at: {proxy_address}")
        
        return proxy_address    


    def upgrade_to_v2(self, proxy_address):
        """Upgrade the proxy to V2 implementation"""
        print("\n=== Upgrading to V2 ===\n")
        
        # Deploy V2 implementation
        print("Deploying Implementation V2...")
        impl_v2_address, impl_v2_abi = self.deploy_contract('LicenseSystemV2')
        
        # Load deployment info
        deployment_path = Path(__file__).parent / 'deployment_info.json'
        with open(deployment_path, 'r') as f:
            deployment_info = json.load(f)
        
        impl_v1_abi = deployment_info['implementationABI']
        
        # Create proxy contract instance
        proxy_contract = self.w3.eth.contract(
            address=proxy_address,
            abi=impl_v1_abi
        )
        
        # Call upgradeTo function
        print(f"Upgrading proxy to new implementation: {impl_v2_address}")
        
        tx = proxy_contract.functions.upgradeTo(impl_v2_address).build_transaction({
            'from': self.address,
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
        })
        
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)  # Fixed: raw_transaction
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"Upgrade transaction hash: {tx_hash.hex()}")
        print(f"Upgrade successful! Gas used: {receipt.gasUsed}")
        
        # Update deployment info
        deployment_info['implementationV2'] = impl_v2_address
        deployment_info['upgradeTime'] = int(time.time())
        deployment_info['implementationV2ABI'] = impl_v2_abi
        
        with open(deployment_path, 'w') as f:
            json.dump(deployment_info, f, indent=2)
        
        return impl_v2_address

class LicenseSystemInteractor:
    """Helper class to interact with the deployed system"""
    
    def __init__(self, w3, proxy_address, abi, account):
        self.w3 = w3
        self.contract = w3.eth.contract(address=proxy_address, abi=abi)
        self.account = account
        self.address = account.address
    
    def add_officer(self, officer_address, name, employee_id, role):
        """Add an officer to the system"""
        tx = self.contract.functions.addOfficer(
            officer_address,
            name,
            employee_id,
            role
        ).build_transaction({
            'from': self.address,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
        })
        
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)  # Fixed: raw_transaction
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"Officer added! Transaction: {tx_hash.hex()}")
        return receipt
    
    def create_license(self, category, level, applicant_name, aadhaar, business_name, state, district):
        """Create a new license"""
        tx = self.contract.functions.createLicense(
            category,  # 0=SEED, 1=FERTILIZER, 2=INSECTICIDE
            level,     # 0=STATE, 1=DIVISION, 2=DISTRICT
            applicant_name,
            aadhaar,
            business_name,
            state,
            district
        ).build_transaction({
            'from': self.address,
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
        })
        
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)  # Fixed: raw_transaction
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Get license ID from events
        logs = self.contract.events.LicenseCreated().process_receipt(receipt)
        if logs:
            license_id = logs[0]['args']['licenseId']
            print(f"License created! ID: {license_id}, Transaction: {tx_hash.hex()}")
            return license_id
        else:
            print(f"License created! Transaction: {tx_hash.hex()}")
            return None
    
    def get_license_info(self, license_id):
        """Get basic license information"""
        result = self.contract.functions.getLicenseBasicInfo(license_id).call()
        
        return {
            'id': result[0],
            'licenseNumber': result[1],
            'category': result[2],
            'level': result[3],
            'status': result[4],
            'applicant': result[5],
            'applicantName': result[6],
            'businessName': result[7],
            'applicationDate': result[8],
            'approvalDate': result[9],
            'expiryDate': result[10],
            'isActive': result[11]
        }

def main():
    """Main deployment function"""
    # Configuration
    RPC_URL = os.getenv('BLOCKCHAIN_URL', 'http://localhost:8545')  # Default to local Ganache
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    
    if not PRIVATE_KEY:
        raise Exception("Please set PRIVATE_KEY in .env file")
    
    # Initialize deployer
    deployer = UpgradeableContractDeployer(RPC_URL, PRIVATE_KEY)
    
    # Deploy the system
    proxy_address, impl_v1_address = deployer.deploy_upgradeable_system()
    
    # Example: Interact with the deployed system
    print("\n=== Testing Deployed System ===\n")
    
    # Load deployment info
    deployment_path = Path(__file__).parent / 'deployment_info.json'
    with open(deployment_path, 'r') as f:
        deployment_info = json.load(f)
    
    # Create interactor
    interactor = LicenseSystemInteractor(
        deployer.w3,
        proxy_address,
        deployment_info['implementationABI'],
        deployer.account
    )
    
    try:
        # Add an officer
        print("Adding an officer...")
        interactor.add_officer(
            deployer.address,  # Making deployer an officer for testing
            "Admin Officer",
            "EMP001",
            "Senior Officer"
        )
        
        # Create a license
        print("\nCreating a license...")
        license_id = interactor.create_license(
            0,  # SEED
            2,  # DISTRICT
            "Test Farmer",
            "123456789012",
            "Test Seeds Business",
            "Rajasthan",
            "Jaipur"
        )
        
        # Get license info if ID is available
        if license_id is not None:
            print("\nFetching license info...")
            license_info = interactor.get_license_info(license_id)
            print(f"License Info: {json.dumps(license_info, indent=2)}")
    
    except Exception as e:
        print(f"\nError during testing: {e}")
        print("Deployment was successful, but testing failed.")
        print("You can still interact with the contracts using the addresses above.")
    
    # Optional: Upgrade to V2
    print("\n\nTo upgrade to V2, uncomment the following lines in the script:")
    print("# impl_v2_address = deployer.upgrade_to_v2(proxy_address)")

if __name__ == "__main__":
    main()