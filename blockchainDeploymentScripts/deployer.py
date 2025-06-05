import json
import os
import sys
import datetime
from web3 import Web3
from eth_account import Account
from web3.middleware import ExtraDataToPOAMiddleware
# from solcx import compile_standard, install_solc
import solcx
# from connect import load_key_pair, connect_to_polygon_testnet
import logging
from compile_contracts import compile_contracts

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))
# Ensure the required Solidity version is installed
# HOST = os.getenv('HOST')
# PORT = os.getenv('PORT')
# print(HOST, PORT)
from dotenv import load_dotenv
load_dotenv()
RPC_URL = os.getenv('BLOCKCHAIN_URL', 'http://localhost:8545')  # Default to local Ganache
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
SOLC_VERSION = "0.8.22"

#connect to blockcahin

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
address = account.address
# w3 = connect_to_polygon_testnet()
# w3 = Web3(Web3.HTTPProvider("http://" + HOST + ":" + PORT))
# w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
if not w3.is_connected():
    raise Exception("Failed to connect to the network")

# Initialize the accounts

ADMIN_ACCOUNT = account
MANAGER_ACCOUNT = account
OWNER_ACCOUNT = account

print(ADMIN_ACCOUNT.address)
print(MANAGER_ACCOUNT.address)
print(OWNER_ACCOUNT.address)

w3.eth.defaultAccount = OWNER_ACCOUNT.address

# Install SOLC version
logger.debug("setting solc version to %s", SOLC_VERSION)
solcx.install_solc(SOLC_VERSION)
solcx.set_solc_version(SOLC_VERSION)


FILES_TO_COMPILE = [
    # "./contracts/didRegistry.sol",
    "./contracts/ERC1967Proxy.sol",
    "./contracts/LicenseStorage.sol",
    "./contracts/LicenseSystemV1.sol",
    "./contracts/LicenseSystemV2.sol",

]


CONTRACTS = ["ERC1967Proxy",
             "LicenseStorage",
             "LicenseSystemV1",
             "LicenseSystemV2",
             ]
# SKIPPED_CONTRACTS = ["UserManager","TdrStorage","DrcStorage","NomineeStorage"]
# SKIPPED_CONTRACTS = ["UserStorage", "TdrStorage", "NomineeStorage"]
SKIPPED_CONTRACTS = []
logger.info('following files would be compiled')
logger.info(FILES_TO_COMPILE)


def save_compiled_contracts(compiled_contracts):
    file = "./build/compiled_contracts/compiled_contracts.txt"
    os.system("mkdir -p ./build/compiled_contracts")
    f = open(file, 'w+')
    f.write(json.dumps(compiled_contracts))


def get_previous_contracts():
    file = "./build/compiled_contracts/compiled_contracts.txt"
    f = open(file, 'r')
    data = f.read()
    compiled_contracts = json.loads(data)
    return compiled_contracts


def get_compiled_contracts():
    """
    This function returns a dictionary of all the compiled contracts, their ABI and bytecode.
    It uses the solcx library to compile the contracts specified in the FILES_TO_COMPILE variable.
    The returned dictionary has the
    contract name as the key and a dictionary containing the ABI and bytecode as the value.
    Additionally, it saves the contracts to the local storage using the save_contract function.
    :return: A dictionary with contract name as the key and a dictionary containing the ABI and bytecode as the value.
    """

    _compiled_contracts = solcx.compile_files(FILES_TO_COMPILE,
                                              output_values=["abi", "bin"])
    # Formatting dictionary
    compiled_contracts = {}
    for key in _compiled_contracts.keys():
        value = _compiled_contracts.get(key)
        print(key)
        new_key = key.split(":")[1]
        compiled_contracts[new_key] = value
        save_contract(new_key, value)
    # save_compiled_contracts(compiled_contracts)
    compiled_contract = compiled_contracts
    return compiled_contract


def log_dict(d, s=1):
    """
    Prints the dictionary object with proper spacing
    """

    for key in d.keys():
        logger.debug('  ' * s + key)
        if type(d.get(key)) == dict:
            logger.debug(d.get(key), s + 1)
        else:
            logger.debug('  ' * s, d.get(key))


def save_contract(key, value):
    """
    This function saves the ABI and bytecode of a contract to the local storage.
    The ABI is saved in a file named "{key}.abi" in the "./build/abi/" directory,
    and the bytecode is saved in a file named "{key}.bin" in the "./build/bytecode/" directory.
    :param key: The name of the contract
    :param value: A dictionary containing the ABI and bytecode of the contract
    """
    os.system("mkdir -p ./build/abi")
    os.system("mkdir -p ./build/bytecode")
    f_abi = open("./build/abi/" + key + ".abi", 'w+')
    f_bin = open("./build/bytecode/" + key + ".bin", 'w+')
    # logger.debug(type(value.get('abi')))
    # logger.debug(json.dumps(value.get('abi')))
    f_abi.write(json.dumps(value.get('abi')))
    f_abi.close()

    f_bin.write(value.get('bin'))
    f_bin.close()

def deploy_contract(abi, bytecode):
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    # Ensure the constructor accepts arguments
    gas_estimate = contract.constructor().estimate_gas()
    print("Gas estimate is ", gas_estimate)
    transaction = contract.constructor().build_transaction({
        'from': OWNER_ACCOUNT.address,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(OWNER_ACCOUNT.address)
    })
    signed_transaction = OWNER_ACCOUNT.sign_transaction(transaction)

    # Send the signed transaction
    tx_hash = w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt['contractAddress']
    if contract_address is None:
        raise Exception("Contract deployment failed")
    return contract_address

def deploy_all_contracts(compiled_contracts):
    """
    Deploys all the contracts.
    :param compiled_contracts: A dictionary containing compiled contracts, with their ABI and bytecode.
    :return: Dictionary mapping contract names to deployed addresses.
    """
    CONTRACTS = [ "LicenseStorage", "LicenseSystemV1", "LicenseSystemV2"]
    SKIPPED_CONTRACTS = []  # Add any contracts you want to skip here

    addresses_file = "./build/contract_address/addresses.txt"

    # Load existing addresses if available
    if os.path.isfile(addresses_file):
        with open(addresses_file, 'r') as f:
            contract_addresses = json.load(f)
    else:
        os.makedirs(os.path.dirname(addresses_file), exist_ok=True)
        contract_addresses = {}

    for contract in CONTRACTS:
        logger.debug("Deploying contract: %s", contract)

        if contract in SKIPPED_CONTRACTS:
            logger.debug("Contract %s skipped", contract)
            continue

        compiled = compiled_contracts.get(contract)
        if not compiled:
            logger.error("Contract '%s' not found in compiled contracts. Available: %s",
                         contract, list(compiled_contracts.keys()))
            raise ValueError(f"Missing contract: {contract}")

        abi = compiled.get("abi")
        bytecode = compiled.get("bytecode")

        if not abi or not bytecode:
            raise ValueError(f"ABI or bytecode missing for contract: {contract}")

        address = deploy_contract(abi, bytecode)
        contract_addresses[contract] = address
        logger.info("Address for contract %s: %s", contract, address)

    # Save updated addresses
    with open(addresses_file, "w") as f:
        json.dump(contract_addresses, f, indent=2)

    return contract_addresses


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
            category,
            level,
            applicant_name,
            aadhaar,
            business_name,
            state,
            district
        ).build_transaction({
            'from': self.address,
            'gas': 800000,  # increased just in case
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.address),
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        # Decode logs from this contract only
        for log in receipt.logs:
            if log.address.lower() != self.contract.address.lower():
                continue

            try:
                decoded = self.contract.events.LicenseCreated().process_log(log)
                license_id = decoded['args']['licenseId']
                print(f"\nLicense created! ID: {license_id}, Transaction: {tx_hash.hex()}")
                return license_id
            except Exception:
                print(f"License created! Transaction: {tx_hash.hex()}")

        print("\nLicenseCreated event not found")
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
# def move_files_to_backend():
#     logger.info("moving files to backend")
#     # move to backend
#     os.system('rm -r ../../cemilac-auth//blockchain/contracts/')
#     os.system('mkdir -p ../../cemilac-auth//blockchain/contracts/')
#     os.system('cp -r ./build/abi  ../../cemilac-auth//blockchain/contracts/')
#     os.system('cp -r ./build/contract_address  ../../cemilac-auth//blockchain/contracts/')

# def execute_contract_method(f, account):
#     logger.debug("START execute contract for function %s", str(f))
#     gas_estimate = f.estimateGas()
#     transaction = f.buildTransaction({
#         'from'    : OWNER_ACCOUNT.address,
#         'gas'     : gas_estimate,
#         'gasPrice': w3.eth.gasPrice,
#         'nonce'   : w3.eth.getTransactionCount(OWNER_ACCOUNT.address)
#     })
#
#     # buildTransaction()({
#     #     'from': account.address,
#     #     'gas': gas_estimate,
#     #     'gasPrice': w3.eth.gasPrice,
#     #     'nonce': w3.eth.getTransactionCount(account.address)
#     # })
#     signed_transaction = OWNER_ACCOUNT.signTransaction(transaction)
#     tx_hash = w3.eth.sendRawTransaction(signed_transaction.rawTransaction)
#     tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
#     if not tx_receipt.transactionHash.hex():
#         raise Exception("execution failed %s", str(f))
#
# def set_contract_address(contract, _func, address, message):
#     '''
#     This function calls the contract functions with the given address and the message
#     Use of this function is to load another contract into the contract, or set the manager
#     :param contract:  the Contract in which a method is called
#     :param _func: the function name in the above contract
#     :param address: address which is to be passes as agrument
#     :param message: message to show in console on successful execution
#     :return: Nothing.
#     '''
#     func = getattr(contract.functions, _func)
#     logger.debug("UPDATING: %s", message)
#     logger.debug("with address %s", address)
#     print("UPDATING: " + message)
#     print("with address " + str(address))
#     execute_contract_method(func(address), OWNER_ACCOUNT)
#     # sleep(1)
#
# def instantiate(contract_address, compiled_contracts):
#     """
#     Managers of all the functions needs to be instantiated
#
#     """
#     pass
#     # # For user manager
#     tdr_storage_address = contract_address.get('TdrStorage')
#     # user_manager_address = contract_address.get('UserManager')
#     #
#     #
#     # # load tdr manager abi
#     tdr_storage_contract = w3.eth.contract(address=tdr_storage_address,
#                                            abi=compiled_contracts.get('TdrStorage').get('abi'))
#     # user_manager_contract = w3.eth.contract(address=user_manager_address,
#     #                                         abi=compiled_contracts.get('UserManager').get('abi'))
#     #
#     # # # updating storage in tdr manager
#     # # update_tdr_storage_method = tdr_manager_contract.functions.updateTdrStorage(tdr_storage_address)
#     # # logger.debug("updating  tdr storage in tdr manager contract")
#     # # execute_contract_method(update_tdr_storage_method, OWNER_ACCOUNT)
#     #
#     # # updating user manager in tdr manager
#     # set_contract_address(tdr_storage_contract, 'loadTdrStorage', tdr_storage_address,
#     #                      "updating tdr storage in tdr manager contract")
#
#
# def register_did(did, document):
#     # Get the account from the private key
#     contract_addresses={}
#     abi={}
#     with open('./build/contract_address/addresses.txt', 'r') as file:
#         contract_addresses = json.load(file)
#     with open('./build/abi/DIDRegistry.abi', 'r') as file:
#         abi = json.load(file)
#     did_contract_address = contract_addresses.get('DIDRegistry')
#     did_contract = w3.eth.contract(address=did_contract_address,abi=abi)
#     # did_contract_address = '0x0978EBd46e5efC8479b050708837eB5ff19d09b5'
#     # Create the transaction
#     f = did_contract.functions.registerDID(did, document)
#     gas_estimate = f.estimate_gas()
#     transaction = f.build_transaction({
#         'from'    : OWNER_ACCOUNT.address,
#         'gas'     : gas_estimate,
#         'gasPrice': w3.eth.gas_price,
#         'nonce'   : w3.eth.get_transaction_count(OWNER_ACCOUNT.address)
#     })
#
#     # Sign the transaction
#     signed_transaction = OWNER_ACCOUNT.sign_transaction(transaction)
#
#     # Send the signed transaction
#     tx_hash = w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
#     tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
#
#     print(f'DID registered successfully. Transaction hash: {tx_hash.hex()}')
#     print(f'Transaction receipt: {tx_receipt}')
#

def main():
    """
    The main function
    :return:
    """
    # os.system('rm logs.log')
    start_time = st = datetime.datetime.now()
    print("Compiling contracts")
    compiled_contracts = compile_contracts()
    print("Contracts compiled")
    print("Deploying contract")
    # f=open('./build/contract_address/addresses.txt')
    # contract_addresses = json.loads(f.read())
    contract_addresses = deploy_all_contracts(compiled_contracts)
    print("Contracts deployed")
    logger.info(contract_addresses)
    print(json.dumps(contract_addresses))
    # Save addresses
    with open('./build/contract_address/addresses.txt', 'w') as f:
        f.write(json.dumps(contract_addresses))

    # Test interaction with the deployed contracts
    try:
        logger.info("\n=== Testing Contract Interaction ===")

        # Get the proxy address
        proxy_address = contract_addresses.get('LicenseSystemV2')
        if not proxy_address:
            logger.error("No proxy address found, skipping interaction tests")
            return

        # Get the implementation ABI
        license_v2_data = compiled_contracts.get('LicenseSystemV2')
        if not license_v2_data or not isinstance(license_v2_data, dict):
            logger.error("LicenseSystemV2 data not found or invalid")
            return

        impl_abi = license_v2_data.get('abi')
        if not impl_abi:
            logger.error("No implementation ABI found for LicenseSystemV2")
            return

        # Create interactor
        interactor = LicenseSystemInteractor(
            w3,
            proxy_address,
            impl_abi,
            OWNER_ACCOUNT
        )

        # Test adding an officer
        logger.info("Testing: Adding an officer...")
        interactor.add_officer(
            OWNER_ACCOUNT.address,
            "Admin Officer",
            "EMP001",
            "Senior Officer"
        )

        # Test creating a license
        logger.info("Testing: Creating a license...")
        license_id = interactor.create_license(
            0,  # SEED
            2,  # DISTRICT
            "Test Applicant",
            "123456789012",
            "Test Business",
            "Test State",
            "Test District"
        )

        if license_id:
            logger.info("Testing: Getting license info...")
            license_info = interactor.get_license_info(license_id)
            logger.info("License Info: %s", json.dumps(license_info, indent=2))

    except Exception as e:
        logger.error("Error during interaction testing: %s", str(e))
        logger.error("Deployment was successful, but interaction tests failed.")
        raise  # Re-raise if you want to see the full traceback

    end_time = datetime.datetime.now()
    print("total execution time: ", end_time - start_time)
    print("last mined block after instantiation was ", w3.eth.block_number)
    # f = open('./build/contract_address/addresses.txt', 'w')
    # f.write(json.dumps(contract_addresses))
    f.close()
    # move_files_to_backend()
    end_time = datetime.datetime.now()
    # did_contract_address = contract_addresses.get('DIDRegistry')
    # did_contract = w3.eth.contract(address=did_contract_address,abi=compiled_contracts.get('DIDRegistry').get('abi'))
    # did_contract_address = '0x0978EBd46e5efC8479b050708837eB5ff19d09b5'
    # print("instantiating")
    # instantiate(contract_addresses, compiled_contracts)
    # print("total execution time: ", end_time - start_time)
    # b = w3.eth.blockNumber
    # run_all_test()
    print("last mined block after instantiation was ", w3.eth.block_number)


if __name__ == "__main__":
    main()
    # register_did("some did","some document")