# import logging
# from web3 import Web3
# from seed_license.blockchain_services import (
#     get_contract, call_function, call_view_function, get_transaction_status
# )

# logger = logging.getLogger(__name__)

# class DocumentHandler:
#     def __init__(self):
#         self.contract = get_contract("DocumentRegistry")

#     def store_document_hash(self, sha256_hex: str):
#         tx_receipt = call_function(
#             self.contract.functions.storeDocument,
#             Web3.to_bytes(hexstr=sha256_hex)
#         )
#         doc_id = int(tx_receipt.logs[0].topics[1].hex(), 16)
#         return doc_id, tx_receipt

#     def get_document_hash(self, doc_id: int):
#         return Web3.to_hex(call_view_function(
#             self.contract.functions.getDocumentHash, doc_id
#         ))[2:]

#     def verify_document(self, doc_id: int, sha256_hex: str):
#         on_chain_hash = self.get_document_hash(doc_id)
#         return on_chain_hash.lower() == sha256_hex.lower()