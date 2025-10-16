from locust import HttpUser, task, between, events
import random
import json
import time
import logging
import gevent
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
WAIT_MIN, WAIT_MAX = 1, 3

# ---------------- TEST DATA ----------------
applicant_data = [
    {
        "licenseCategory": "SEED",
        "licenseLevel": "DISTRICT",
        "applicantName": "Ravi Kumar",
        "firmName": "Ravi Agro Traders",
        "firmType": "Partnership",
        "cropName": "Wheat",
        "cropVariety": "HD2967",
        "isSeedSelfProduced": False,
        "productionCompany": "Sharma Seeds Pvt Ltd",
    }
]

officer_data = [
    {"name": "Shrawan", "role": "AGRICULTURE_OFFICER"},
    {"name": "Rajesh", "role": "JOINT_DIRECTOR"},
    {"name": "Meena", "role": "DEPUTY_DIRECTOR"},
    {"name": "Arun", "role": "ASSISTANT_DIRECTOR"},
]

status_flow = [
    {"status": "SUBMITTED", "remarks": "Application submitted"},
    {"status": "UNDER_REVIEW", "remarks": "Application under review"},
    {"status": "DOCUMENTS_VERIFIED", "remarks": "Documents verified"},
    {"status": "INSPECTION_SCHEDULED", "remarks": "Inspection scheduled"},
    {"status": "INSPECTION_COMPLETED", "remarks": "Inspection completed"},
    {"status": "APPROVED", "remarks": "License approved", "renewalPeriodDays": 365},
]

# Load encrypted Aadhaar numbers once at startup
try:
    with open('encrypted_aadhaar.json', 'r') as f:
        ENCRYPTED_AADHAARS = json.load(f)
except Exception as e:
    logger.error(f"Failed to load encrypted_aadhaar.json: {e}")
    ENCRYPTED_AADHAARS = ["default_encrypted_aadhaar_123"]

# ---------------- GLOBAL METRICS ----------------
class TestMetrics:
    def __init__(self):
        self.create_ok = 0
        self.create_fail = 0
        self.status_ok = 0
        self.status_fail = 0
        self.qr_ok = 0
        self.qr_fail = 0
        self.verify_ok = 0
        self.verify_fail = 0
        self.count_ok = 0
        self.count_fail = 0
        self.details_ok = 0
        self.details_fail = 0

metrics = TestMetrics()


# ---------------- SMART WAIT STRATEGY ----------------
class SmartWaiter:
    """Advanced waiting strategy with adaptive delays"""
    
    def __init__(self):
        self.response_times = []
        self.error_rates = []
        self.max_history = 100
        
    def adaptive_wait(self, base_min, base_max, recent_errors=0):
        """Adapt wait time based on system performance"""
    
        error_factor = 1 + (recent_errors * 0.5)
        
      
        if self.response_times:
            avg_response = sum(self.response_times) / len(self.response_times)
          
            if avg_response > 5000: 
                wait_factor = 1.5
            elif avg_response > 2000: 
                wait_factor = 1.2
            else:
                wait_factor = 1.0
        else:
            wait_factor = 1.0
            
        adjusted_min = base_min * wait_factor * error_factor
        adjusted_max = base_max * wait_factor * error_factor
        
        return random.uniform(adjusted_min, adjusted_max)
    
    def record_response_time(self, response_time):
        """Record response time for adaptive waiting"""
        self.response_times.append(response_time)
        if len(self.response_times) > self.max_history:
            self.response_times.pop(0)
    
    def record_error(self):
        """Record error for backoff strategy"""
        self.error_rates.append(1)
        if len(self.error_rates) > self.max_history:
            self.error_rates.pop(0)
    
    def get_recent_errors(self, window=10):
        """Get number of recent errors"""
        return sum(self.error_rates[-window:]) if self.error_rates else 0

smart_waiter = SmartWaiter()

# ---------------- ASYNC HELPERS ----------------
def async_sleep(seconds):
    """Non-blocking sleep using gevent"""
    gevent.sleep(seconds)

def execute_with_timeout(func, timeout=30, *args, **kwargs):
    """Execute function with timeout"""
    try:
        with gevent.Timeout(timeout):
            return func(*args, **kwargs)
    except gevent.Timeout:
        logger.warning(f"Operation timed out after {timeout} seconds")
        return None

# ---------------- HELPERS ----------------
def random_item(arr):
    return random.choice(arr)

def random_int(min_val, max_val):
    return random.randint(min_val, max_val)

def safe_json(res):
    try:
        return res.json()
    except Exception as e:
        logger.warning(f"JSON parse error: {e}")
        return {}

def generate_application():
    base = random_item(applicant_data)
    return {
        **base,
        "aadhaarNumber": random_item(ENCRYPTED_AADHAARS),
        "registeringAuthority": "Department of Agriculture",
        "registeringOfficeName": f"District Agri Office, {random_item(['Jaipur','Udaipur','Jodhpur','Kota'])}",
        "applicantPermanentAddress": f"H.No {random_int(1,100)}, {random_item(['Green','Royal','Sunrise'])} Colony",
        "firmAddress": f"Plot No {random_int(1,50)}, {random_item(['Mandi Road','Industrial Area','Agro Park'])}",
        "salePointAddress": f"Shop No {random_int(1,20)}, {random_item(['Krishi Market','Farmer Plaza','Agri Complex'])}",
        "saleStorageAddress": f"Warehouse {random_int(1,10)}, {random_item(['Outer Ring Road','Storage Zone','Logistics Park'])}"
    }

def parse_error_response(response):
    """Parse error response to get meaningful error message"""
    try:
        data = safe_json(response)
        if data.get("data") and isinstance(data["data"], dict):
            return data["data"].get("details", data["data"].get("error", "Unknown error"))
        return data.get("error", "Unknown error")
    except:
        return response.text[:200]

# ---------------- REQUEST HANDLERS ----------------
def handle_create_license(user, payload):
    """Handle license creation with proper metrics"""
    start_time = time.time()
    with user.client.post("/license/create/", json=payload, headers={"Content-Type": "application/json"}, catch_response=True, name="/license/create") as response:
        response_time = (time.time() - start_time) * 1000
        smart_waiter.record_response_time(response_time)
        
        if response.status_code in [200, 201, 202]:
            metrics.create_ok += 1
            response.success()
            logger.info(f"✅ License creation successful: {response.status_code}")
            return True
        else:
            metrics.create_fail += 1
            smart_waiter.record_error()
            error_msg = parse_error_response(response)
            response.failure(f"Status: {response.status_code}, Error: {error_msg}")
            logger.error(f"❌ License creation failed: {response.status_code} - {error_msg}")
            return False

def handle_get_license_count(user):
    """Handle license count retrieval with retry logic"""
    for attempt in range(3):
        start_time = time.time()
        with user.client.get("/license/count/", catch_response=True, name="/license/count") as response:
            response_time = (time.time() - start_time) * 1000
            smart_waiter.record_response_time(response_time)
            
            if response.status_code == 200:
                metrics.count_ok += 1
                response.success()
                data = safe_json(response)
                count = data.get("data", 0)
                logger.debug(f"📊 License count: {count}")
                return count
            else:
                if attempt == 2:  
                    metrics.count_fail += 1
                    smart_waiter.record_error()
                    response.failure(f"Status: {response.status_code}")
                async_sleep(2 ** attempt) 
    return 0

def handle_get_license_details(user, license_id):
    """Handle license details retrieval"""
    start_time = time.time()
    with user.client.get(f"/license/info/{license_id}/", catch_response=True, name="/license/info/license_id") as response:
        response_time = (time.time() - start_time) * 1000
        smart_waiter.record_response_time(response_time)
        
        if response.status_code == 200:
            metrics.details_ok += 1
            response.success()
            data = safe_json(response)
            license_data = data.get("data", {})
            if license_data:
                logger.debug(f"📄 License {license_id} details: {license_data.get('status', 'UNKNOWN')}")
            return license_data
        else:
            metrics.details_fail += 1
            smart_waiter.record_error()
            response.failure(f"Status: {response.status_code}")
            return None

def handle_update_status(user, payload, license_id):
    """Handle status update with retry logic"""
    for attempt in range(3):
        start_time = time.time()
        with user.client.post("/license/update-status/", json=payload, headers={"Content-Type": "application/json"}, catch_response=True, name="/license/update-status") as response:
            response_time = (time.time() - start_time) * 1000
            smart_waiter.record_response_time(response_time)
            
            if response.status_code in [200, 202]:
                metrics.status_ok += 1
                response.success()
                logger.info(f"✅ Status update successful for license {license_id}")
                return True
            elif "gas limit" in response.text.lower():
                delay = 2 ** attempt * random.randint(2, 5)
                logger.warning(f"⚠️ Gas limit exceeded for license {license_id}, retrying in {delay}s")
                async_sleep(delay)  
            else:
                if attempt == 2: 
                    metrics.status_fail += 1
                    smart_waiter.record_error()
                    error_msg = parse_error_response(response)
                    response.failure(f"Status: {response.status_code}, Error: {error_msg}")
                    logger.error(f"❌ Status update failed for license {license_id}: {response.status_code} - {error_msg}")
                return False
    return False

def handle_get_qr(user, license_id):
    """Handle QR code retrieval"""
    start_time = time.time()
    with user.client.get(f"/license/qr/{license_id}/", catch_response=True, name="/license/qr/license_id") as response:
        response_time = (time.time() - start_time) * 1000
        smart_waiter.record_response_time(response_time)
        
        if response.status_code in [200, 202]:
            metrics.qr_ok += 1
            response.success()
            data = safe_json(response)
            qr_data = data.get("data", {})
            logger.debug(f"📦 QR data for {license_id}: {qr_data}")
            return qr_data
        else:
            metrics.qr_fail += 1
            smart_waiter.record_error()
            response.failure(f"Status: {response.status_code}")
            return None

def handle_verify_license(user, payload):
    """Handle license verification"""
    start_time = time.time()
    with user.client.post("/license/verify/", json=payload, headers={"Content-Type": "application/json"}, catch_response=True, name="/license/verify") as response:
        response_time = (time.time() - start_time) * 1000
        smart_waiter.record_response_time(response_time)
        
        if response.status_code in [200, 202]:
            metrics.verify_ok += 1
            response.success()
            logger.info(f"🔐 License verification successful")
            return True
        else:
            metrics.verify_fail += 1
            smart_waiter.record_error()
            response.failure(f"Status: {response.status_code}")
            return False

# ---------------- LOCUST USER ----------------
class SeedLicensingUser(HttpUser):
    wait_time = between(WAIT_MIN, WAIT_MAX)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recent_errors = 0
        self.error_window = []

    def adaptive_wait(self, min_time, max_time):
        """Use smart waiting strategy"""
        recent_errors = smart_waiter.get_recent_errors()
        wait_time = smart_waiter.adaptive_wait(min_time, max_time, recent_errors)
        async_sleep(wait_time)

    @task(3)  
    def citizen_submit_license(self):
        """Citizen submits a new license application"""
        payload = generate_application()
        success = handle_create_license(self, payload)
        
        if success:
            logger.info("✅ License creation successful")
        else:
            logger.error("❌ License creation failed")
     
        self.adaptive_wait(1.5, 3.5)

    @task(7) 
    def officer_workflow(self):
        """Officer performs license workflow updates"""
        try:
            # Get total licenses
            total_licenses = handle_get_license_count(self)
            if total_licenses == 0:
                logger.info("📭 No licenses available for processing")
                self.adaptive_wait(1, 2)
                return
            
           
            license_id = random_int(1, total_licenses) if total_licenses > 0 else None
            if not license_id:
                logger.warning("⚠️ No valid license ID found for update")
                self.adaptive_wait(1, 2)
                return
            
            # Get license details
            license_data = handle_get_license_details(self, license_id)
            if not license_data:
                logger.warning(f"⚠️ Could not fetch details for license {license_id}")
                self.adaptive_wait(0.5, 1)
                return
            
            current_status = license_data.get("status")
            logger.info(f"📋 License {license_id} current status: {current_status}")
            
            # Check if license is in final state
            if current_status in ["APPROVED", "REJECTED", "REVOKED"]:
                logger.debug(f"📄 License {license_id} is already in final state: {current_status}")
                self.adaptive_wait(0.5, 1)
                return

            # Find current status in flow and determine next status
            current_idx = next((i for i, s in enumerate(status_flow) if s["status"] == current_status), -1)
            if current_idx == -1:
                logger.warning(f"⚠️ License {license_id} has unknown status: {current_status}")
                self.adaptive_wait(0.5, 1)
                return
                
            if current_idx + 1 >= len(status_flow):
                logger.debug(f"📄 License {license_id} has no next status from: {current_status}")
                self.adaptive_wait(0.5, 1)
                return

            next_status = status_flow[current_idx + 1]
            officer = random_item(officer_data)
            
            # Prepare payload 
            payload = {
                "licenseId": license_id,
                "status": next_status["status"],
                "officerName": officer["name"],
                "role": officer["role"],
                "remarks": next_status["remarks"],
            }
            
            # Add renewal period only for APPROVED status
            if next_status["status"] == "APPROVED":
                payload["renewalPeriodDays"] = next_status.get("renewalPeriodDays", 365)

            logger.info(f"🔄 License {license_id}: {current_status} → {next_status['status']}")

            # Update status
            update_success = handle_update_status(self, payload, license_id)
            
            if update_success and next_status["status"] == "APPROVED":
                self.adaptive_wait(0.5, 1.5)
                
                # Get QR code for approved license
                qr_data = handle_get_qr(self, license_id)
                if qr_data and qr_data.get("licenseNumber") and qr_data.get("verificationHash"):
                    logger.info(f"🔍 QR Code retrieved for License {license_id}")
                    
                    # Verify license
                    verify_payload = {
                        "licenseNumber": qr_data["licenseNumber"],
                        "expectedHash": qr_data["verificationHash"]
                    }
                    verify_success = handle_verify_license(self, verify_payload)
                    if verify_success:
                        logger.info(f"🔐 License {license_id} verified successfully")
                    else:
                        logger.error(f"❌ License {license_id} verification failed")
                else:
                    logger.warning(f"⚠️ Could not retrieve QR data for license {license_id}")
            
            elif not update_success:
                logger.error(f"❌ Status update failed for license {license_id}")

            self.adaptive_wait(1, 3)

        except Exception as e:
            logger.error(f"❌ Officer workflow exception: {e}")
            smart_waiter.record_error()
            self.adaptive_wait(1, 2)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    logger.info("🌿 Starting Rajasthan Seed Licensing Stress Test")
    try:
        base_url = environment.host 
        response = requests.get(f"{base_url}/owner/", timeout=10)
        if response.status_code == 200:
            logger.info("✅ Backend is reachable (global check)")
        else:
            logger.error(f"❌ Backend connectivity issue: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Backend not reachable: {e}")



