import random
import logging
from locust import HttpUser, task, between, LoadTestShape


# Logging setup
logger = logging.getLogger("locust")
logger.setLevel(logging.INFO)


# Test Data
applicant_data = [
    {
        "license_category": "SEED",
        "license_level": "DISTRICT",
        "applicant_name": "Ravi Kumar",
        "aadhaar_number": "299788776655",
        "firm_name": "Ravi Agro Traders",
        "firm_type": "Partnership",
        "crop_name": "Wheat",
        "crop_variety": "HD2967",
        "is_seed_self_produced": False,
        "production_company": "Sharma Seeds Pvt Ltd"
    },
    {
        "license_category": "SEED",
        "license_level": "STATE",
        "applicant_name": "Priya Sharma",
        "aadhaar_number": "299788776654",
        "firm_name": "Sharma Seeds",
        "firm_type": "Proprietorship",
        "crop_name": "Rice",
        "crop_variety": "PR126",
        "is_seed_self_produced": True,
        "production_company": "Sharma Seeds Pvt Ltd"
    },
    {
        "license_category": "SEED",
        "license_level": "DISTRICT",
        "applicant_name": "Vijay Singh",
        "aadhaar_number": "289738671284",
        "firm_name": "Vijay Agro",
        "firm_type": "LLP",
        "crop_name": "Maize",
        "crop_variety": "PMH1",
        "is_seed_self_produced": False,
        "production_company": "Sharma Seeds Pvt Ltd"
    }
]

officer_data = [
    {"name": "Shrawan", "role": "AGRICULTURE_OFFICER"},
    {"name": "Rajesh", "role": "JOINT_DIRECTOR"},
    {"name": "Meena", "role": "DEPUTY_DIRECTOR"},
    {"name": "Arun", "role": "DIRECTOR"}
]

status_flow = [
    {"status": "SUBMITTED", "remarks": "Application submitted"},
    {"status": "UNDER_REVIEW", "remarks": "Application under review"},
    {"status": "DOCUMENTS_VERIFIED", "remarks": "Documents verified"},
    {"status": "INSPECTION_SCHEDULED", "remarks": "Inspection scheduled"},
    {"status": "INSPECTION_COMPLETED", "remarks": "Inspection completed"},
    {"status": "APPROVED", "remarks": "License approved", "renewal_period_days": 365}
]


# Helper functions
def random_item(data):
    return random.choice(data)

def random_int(min_val, max_val):
    return random.randint(min_val, max_val)


def generate_aadhaar():
    first_digit = str(random.randint(2, 9))
    rest_digits = ''.join(str(random.randint(0, 9)) for _ in range(11))
    return first_digit + rest_digits

def generate_application():
    base = random_item(applicant_data)
    base_copy = base.copy()
    base_copy["aadhaar_number"] = generate_aadhaar()  
    return {
        **base_copy,
        "registering_authority": "Department of Agriculture",
        "registering_office_name": f"District Agri Office, {random.choice(['Jaipur','Udaipur','Jodhpur','Kota'])}",
        "applicant_permanent_address": f"H.No {random_int(1,100)}, {random.choice(['Green','Royal','Sunrise'])} Colony",
        "firm_address": f"Plot No {random_int(1,50)}, {random.choice(['Mandi Road','Industrial Area','Agro Park'])}",
        "sale_point_address": f"Shop No {random_int(1,20)}, {random.choice(['Krishi Market','Farmer Plaza','Agri Complex'])}",
        "sale_storage_address": f"Warehouse {random_int(1,10)}, {random.choice(['Outer Ring Road','Storage Zone','Logistics Park'])}"
    }


# Locust User
class SeedLicenseUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://127.0.0.1:8000/api/blockchain"

    @task
    def citizen_or_officer_flow(self):
        if random.choice([True, False]):
            self.citizen_flow()
        else:
            self.officer_flow()

    def citizen_flow(self):
        payload = generate_application()
        logger.info(f"Submitting application for {payload['applicant_name']}")
        with self.client.post("/license/create/", json=payload, catch_response=True) as res:
            if res.status_code in [200, 201, 202]:
                res.success()
                logger.info("Application submitted successfully")
            else:
                res.failure(f"Application failed: {res.text}")

    def officer_flow(self):
        with self.client.get("/license/count/", catch_response=True) as res:
            if res.status_code != 200:
                res.failure("Failed to fetch license count")
                return
            license_count = res.json().get("data", {}).get("count", 0)

        if license_count <= 0:
            return

        license_id = random_int(1, license_count)
        logger.info(f"Processing license {license_id}")

        with self.client.get(f"/license/{license_id}/info/", catch_response=True) as res:
            if res.status_code != 200:
                res.failure("Failed to fetch license info")
                return
            license_info = res.json().get("data")

        if not license_info:
            return

        terminal_statuses = ["APPROVED", "REJECTED", "REVOKED", "EXPIRED"]
        if license_info.get("status") in terminal_statuses:
            return

        current_status_index = next(
            (i for i, s in enumerate(status_flow) if s["status"] == license_info.get("status")), -1
        )
        next_status = status_flow[current_status_index + 1] if current_status_index >= 0 else None

        if not next_status:
            return

        officer = random_item(officer_data)
        update_payload = {
            "license_id": license_id,
            "status": next_status["status"],
            "officer_name": officer["name"],
            "role": officer["role"],
            "remarks": next_status["remarks"]
        }
        if next_status["status"] == "APPROVED":
            update_payload["renewal_period_days"] = next_status["renewal_period_days"]

        with self.client.post("/license/update-status/", json=update_payload, catch_response=True) as res:
            if res.status_code == 200:
                res.success()
                logger.info(f"License {license_id} updated to {next_status['status']}")
            else:
                res.failure(f"Status update failed: {res.text}")
                return

        if next_status["status"] == "APPROVED":
            with self.client.get(f"/license/{license_id}/qr/", catch_response=True) as qr_res:
                if qr_res.status_code != 200:
                    qr_res.failure("QR fetch failed")
                    return
                qr_data = qr_res.json()

            verify_payload = {
                "license_number": qr_data.get("licenseNumber"),
                "expected_hash": qr_data.get("verificationHash")
            }
            with self.client.post("/license/verify/", json=verify_payload, catch_response=True) as v_res:
                if v_res.status_code == 200:
                    v_res.success()
                    logger.info(f"License {license_id} verified successfully")
                else:
                    v_res.failure("Verification failed")


# Stress Test Shape
class StepLoadShape(LoadTestShape):
    stages = [
        {"duration": 30, "users": 50},
        {"duration": 30, "users": 200},
        {"duration": 30, "users": 500},
        {"duration": 30, "users": 500},
        {"duration": 30, "users": 500},
        {"duration": 30, "users": 0},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], 1)
        return None
