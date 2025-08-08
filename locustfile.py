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
        "licenseLevel": "DISTRICT",
        "registeringAuthority": "Department of Agriculture",
        "registeringOfficeName": "District Agri Office, Jaipur",
        "applicantName": "Ravi Kumar",
        "aadhaarNumber": "123456789012",
        "applicantPermanentAddress": "H.No 45, Green Colony, Jaipur",
        "firmName": "Ravi Agro Traders",
        "firmType": "Partnership",
        "firmAddress": "Plot No 22, Mandi Road, Jaipur",
        "salePointAddress": "Shop No 5, Krishi Market, Jaipur",
        "saleStorageAddress": "Warehouse No 3, Outer Ring Road, Jaipur",
        "cropName": "Wheat",
        "cropVariety": "HD2967",
        "isSeedSelfProduced": False,
        "productionCompany": "Agro Seeds Pvt Ltd"
    }

    # Status update payload (for officers)
    update_status_payload = {
        "licenseId": 2,
        "status": "UNDER_REVIEW",
        "officerName": "Shrawan",
        "role": "AGRICULTURE_OFFICER",
        "renewalPeriodDays": 34,
        "remarks": "License is UNDER_REVIEW"
    }

    # Verify license payload
    verify_payload = {
        "licenseNumber": "RJSDST1",
        "expectedHash": "212d02520d33be03153a2c34cb4d50b63f570e6d6881589ebbec2ec6b3da51b0"
    }

    # Update license details
    update_payload = {
        "license_id": 1,
        "firm_name": "New Firm Name",
        "firm_type": "New Firm Type",
        "firm_address": "New Firm Address",
        "sale_point_address": "New Sale Point Address",
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
    def license_verify(self):
        self.request("POST", "/api/blockchain/verify-document/",
                     data=json.dumps(self.verify_payload),
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
