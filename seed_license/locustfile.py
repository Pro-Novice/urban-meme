from locust import HttpUser, task, between
import random
import string

def random_string(length=6):
    return ''.join(random.choices(string.ascii_letters, k=length))

class LicenseBlockchainUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def initialize_blockchain(self):
        self.client.get("/api/blockchain/owner/")

    @task
    def check_owner(self):
        self.client.get("/api/blockchain/owner/")

    @task
    def license_count(self):
        self.client.get("/api/blockchain/license/count/")

    @task
    def submit_license_application(self):
        payload = {
            "license_category": "AGRICULTURE",
            "license_level": "STATE",
            "registering_authority": "JOINT_DIRECTOR",
            "registering_office_name": "Office " + random_string(),
            "applicant_name": "User " + random_string(),
            "aadhaar_number": str(random.randint(100000000000, 999999999999)),
            "applicant_permanent_address": "Address " + random_string(),
            "firm_name": "Firm " + random_string(),
            "firm_type": "LLP",
            "firm_address": "Firm Addr " + random_string(),
            "sale_point_address": "Sale Addr",
            "sale_storage_address": "Storage Addr",
            "production_company": "Company X",
            "crop_name": "Wheat",
            "crop_variety": "Golden"
        }
        self.client.post("/api/blockchain/license/create/", json=payload)

    @task
    def verify_license_document(self):
        payload = {
            "license_number": "1",  # Adjust or randomize if needed
            "expected_hash": "dummyhashvalue123456789"
        }
        self.client.post("/api/blockchain/license/verify/", json=payload)

    @task
    def update_license_details(self):
        payload = {
            "license_id": 1,
            "firm_name": "Updated Firm",
            "firm_type": "PVT",
            "firm_address": "Updated Addr",
            "sale_point_address": "Updated Sale",
            "sale_storage_address": "Updated Storage",
            "production_company": "Updated Co",
            "crop_name": "Corn",
            "crop_variety": "Sweet",
            "role": "JOINT_DIRECTOR"
        }
        self.client.post("/api/blockchain/license/update/", json=payload)

    @task
    def get_license_basic_info(self):
        license_id = random.randint(1, 5)
        self.client.get(f"/api/blockchain/license/{license_id}/info/")

    @task
    def get_license_action_history(self):
        license_id = random.randint(1, 5)
        self.client.get(f"/api/blockchain/license/{license_id}/history/")

    @task
    def get_license_qr_data(self):
        license_id = random.randint(1, 5)
        self.client.get(f"/api/blockchain/license/{license_id}/qr/")

    @task
    def update_license_status(self):
        payload = {
            "license_id": 1,
            "status": "APPROVED",  # use valid enum
            "remarks": "All documents verified.",
            "officer_name": "Officer X",
            "role": "JOINT_DIRECTOR",
            "renewal_period_days": 365
        }
        self.client.post("/api/blockchain/license/update-status/", json=payload)

    @task
    def get_transaction_status(self):
        tx_hash = "0x" + "".join(random.choices("abcdef1234567890", k=64))  # dummy hash
        self.client.get(f"/api/blockchain/transaction/{tx_hash}/")

    @task
    def get_contract_address(self):
        self.client.get("/api/blockchain/contract/LicenseSystemV1/address/")

    @task
    def get_all_contract_methods(self):
        self.client.get("/api/blockchain/contract/LicenseSystemV1/methods/")

    @task
    def get_contract_abi(self):
        self.client.get("/api/blockchain/contract/LicenseSystemV1/abi/")
