import json
import os
from datetime import datetime
from web3 import Web3
from eth_account import Account
from pathlib import Path
from dotenv import load_dotenv

proxy_admin_abi = [
    {
        "inputs": [{"internalType": "address", "name": "newImplementation", "type": "address"}],
        "name": "upgradeTo",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# Load env variables
load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL")

# Web3 setup
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
chain_id = w3.eth.chain_id


def load_artifact(contract_name):
    path = f'./artifacts/{contract_name}.json'
    with open(path, 'r') as f:
        data = json.load(f)
        return data['abi'], data['bytecode']


def deploy_contract(abi, bytecode, constructor_args=()):
    nonce = w3.eth.get_transaction_count(account.address)
    tx = {
        'from': account.address,
        'nonce': nonce,
        'gas': 7_000_000,
        'gasPrice': w3.eth.gas_price,
        'chainId': chain_id
    }
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_data = contract.constructor(*constructor_args).build_transaction(tx)
    signed_tx = w3.eth.account.sign_transaction(tx_data, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt.contractAddress


def call_contract_function(contract_address, abi, function_name, args=()):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    func = contract.functions[function_name](*args)
    nonce = w3.eth.get_transaction_count(account.address)
    tx = func.build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 2_000_000,
        'gasPrice': w3.eth.gas_price,
        'chainId': chain_id
    })
    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def save_deployment_info(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"\n💾 Saved deployment info to {filename}")


def main():
    print("🚀 Deploying LicenseSystemV1...")
    license_v1_abi, license_v1_bytecode = load_artifact("LicenseSystemV1")
    license_v1_address = deploy_contract(license_v1_abi, license_v1_bytecode)
    print(f"✓ LicenseSystemV1 deployed at: {license_v1_address}")

    print("\n⚙️ Preparing initializer data...")
    license_v1_contract = w3.eth.contract(address=license_v1_address, abi=license_v1_abi)
    init_data = license_v1_contract.functions.initialize()._encode_transaction_data()

    print("📦 Deploying ERC1967Proxy with LicenseSystemV1 as implementation...")
    proxy_abi, proxy_bytecode = load_artifact("ERC1967Proxy")
    proxy_address = deploy_contract(proxy_abi, proxy_bytecode, constructor_args=(license_v1_address, init_data))
    print(f"✓ Proxy deployed at: {proxy_address}")

    print("\n✅ Proxy initialized with V1. You can now interact with it using V1 ABI.")

    print("\n🚀 Deploying LicenseSystemV2...")
    license_v2_abi, license_v2_bytecode = load_artifact("LicenseSystemV2")
    license_v2_address = deploy_contract(license_v2_abi, license_v2_bytecode)
    print(f"✓ LicenseSystemV2 deployed at: {license_v2_address}")

    print("\n🔁 Upgrading proxy to LicenseSystemV2...")
    proxy_admin_contract = w3.eth.contract(address=proxy_address, abi=proxy_admin_abi)
    upgrade_tx = proxy_admin_contract.functions.upgradeTo(license_v2_address).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 500000,
        "gasPrice": w3.to_wei("20", "gwei"),
        "chainId": chain_id
    })
    signed_upgrade_tx = w3.eth.account.sign_transaction(upgrade_tx, PRIVATE_KEY)
    upgrade_tx_hash = w3.eth.send_raw_transaction(signed_upgrade_tx.raw_transaction)
    upgrade_receipt = w3.eth.wait_for_transaction_receipt(upgrade_tx_hash)
    print(f"✓ Proxy upgraded to LicenseSystemV2 at tx: {upgrade_tx_hash.hex()}")

    # Save info
    deployment_info = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "deployer": account.address,
        "chain_id": chain_id,
        "implementationV1": license_v1_address,
        "implementationV2": license_v2_address,
        "proxy": proxy_address,
        "upgradeTxHash": upgrade_tx_hash.hex(),
        "implementationABI": license_v2_abi
    }

    deployment_path = Path(__file__).parent / 'deployment_info.json'
    save_deployment_info(deployment_path, deployment_info)

    print("\n🎉 Deployment and upgrade complete!")
    print(f"🧠 Proxy address (interact with this): {proxy_address}")
    print(f"🔗 Current implementation: {license_v2_address}")


if __name__ == "__main__":
    main()