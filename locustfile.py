from locust import HttpUser, task, between
import random
import json

class BlockchainUser(HttpUser):
    wait_time = between(1, 2)

    # List of validator URLs
    validator_nodes = [
        "http://10.70.233.247:8545",
        "http://10.70.233.248:8545",
        "http://10.70.233.249:8545",
        "http://10.70.233.250:8545",
    ]

    # Dummy request bodies — replace with your actual payloads
    create_payload = {
    "licenseCategory": "SEED",
    "adminLevel": "DIVISION",
    "applicantName": "Ravi Kumar",
    "aadhaarNumber": "123456789012",
    "businessName": "Kumar Seeds & Agriculture",
    "division": "udaipur"
    }

    update_status_payload = {        
    "licenseId":2,
    "status":"submitted",//DRAFT, SUBMITTED, UNDER_REVIEW, DOCUMENTS_VERIFIED, PAYMENT_PENDING, PAYMENT_COMPLETED, INSPECTION_SCHEDULED
    "remarks":"License is submitted"
}

    update_payload = {
    // license_id and role are required fields, rest ae optional but atleast there should be 1 field to update
    "license_id": 1,
    "firm_name": "New Firm Name",
    "firm_type": "New Firm Type",
    "firm_address": "New Firm Address",
    "sale_point_address": "New Sale Point Address",
    // "sale_storage_address": "New Sale Storage Address",
    // "production_company": "New Production Company",
    // "crop_name": "New Crop Name",
    "crop_variety": "New Crop Variety",
    "role": "JOINT_DIRECTOR"
}

    def request(self, method, path, **kwargs):
        base_url = random.choice(self.validator_nodes)
        full_url = f"{base_url}{path}"
        return self.client.request(method, full_url, **kwargs)

    @task
    def initialize(self):
        self.request("GET", "/api/blockchain/initialize/")

    @task
    def owner(self):
        self.request("GET", "/api/blockchain/owner/")

    @task
    def license_count(self):
        self.request("GET", "/api/blockchain/license/count/")

    @task
    def license_create(self):
        self.request("POST", "/api/blockchain/license/create/", 
                     data=json.dumps(self.create_payload),
                     headers={"Content-Type": "application/json"})

    @task
    def license_update_status(self):
        self.request("POST", "/api/blockchain/license/update-status/", 
                     data=json.dumps(self.update_status_payload),
                     headers={"Content-Type": "application/json"})

    @task
    def license_update(self):
        self.request("POST", "/api/blockchain/license/update/", 
                     data=json.dumps(self.update_payload),
                     headers={"Content-Type": "application/json"})

    @task
    def license_info(self):
        self.request("GET", "/api/blockchain/license/1/info/")

    @task
    def license_history(self):
        self.request("GET", "/api/blockchain/license/1/history/")
