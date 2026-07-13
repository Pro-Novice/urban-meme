from locust import HttpUser, task, between, events, constant, tag
import random
import json
import time
import logging
import gevent
import requests
import os


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8000/api/blockchain')
RPC_URLS = os.getenv('RPC_URLS', 'http://host.docker.internal:8545').split(',')
CONTRACT_ADDRESSES = os.getenv('CONTRACT_ADDRESSES', '').split(',')
JSON_HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}

# ---------------- SHARED DATA ----------------
# Load encrypted Aadhaar numbers
try:
    base_dir = os.path.dirname(__file__)
    aadhaar_path = os.path.join(base_dir, 'encrypted_aadhaar.json')
    with open(aadhaar_path, 'r') as f:
        ENCRYPTED_AADHAARS = json.load(f)
        if not isinstance(ENCRYPTED_AADHAARS, list):
            logger.warning("encrypted_aadhaar.json does not contain a list — using default")
            ENCRYPTED_AADHAARS = ['default_encrypted_aadhaar']
except Exception as e:
    logger.warning(f"Failed to load encrypted_aadhaar.json: {e}")
    ENCRYPTED_AADHAARS = ['default_encrypted_aadhaar']

# Test data
applicant_data = [
    {
        "licenseCategory": "SEED",
        "applicationLicenseType": "NEW_APPLICATION",
        "licenseLevel": "DISTRICT",
        "applicantName": "Ravi Kumar",
        "firmName": "Ravi Agro Traders",
        "firmType": "Partnership",
        "cropName": ["Wheat", "Rice", "Maize"],
        "cropVariety": "HD2967",
        "isSeedSelfProduced": False,
        "productionCompany": "Sharma Seeds Pvt Ltd",
        "latitude": 26.9124,
        "longitude": 75.7873,
    },
    {
        "licenseCategory": "FERTILIZER",
        "applicationLicenseType": "RETAIL_DEALER",
        "licenseLevel": "STATE",
        "applicantName": "Priya Sharma",
        "firmName": "Green Earth Fertilizers",
        "firmType": "Private Limited",
        "cropName": ["Rice"],
        "cropVariety": "Basmati",
        "isSeedSelfProduced": False,
        "productionCompany": "AgroTech Ltd",
        "latitude": 27.0238,
        "longitude": 74.2179,
    }
]

officer_data = [
    {"name": "Shrawan", "role": "AGRICULTURE_OFFICER"},
    {"name": "Rajesh", "role": "JOINT_DIRECTOR"},
    {"name": "Meena", "role": "DEPUTY_DIRECTOR"},
    {"name": "Arun", "role": "ASSISTANT_DIRECTOR"},
]

status_flow = [
    {"status": "SUBMITTED", "remarks": "Application submitted", "next": ["UNDER_REVIEW"]},
    {"status": "UNDER_REVIEW", "remarks": "Application under review", "next": ["DOCUMENTS_VERIFIED", "REJECTED"]},
    {"status": "DOCUMENTS_VERIFIED", "remarks": "Documents verified successfully", "next": ["INSPECTION_SCHEDULED"]},
    {"status": "INSPECTION_SCHEDULED", "remarks": "Inspection scheduled", "next": ["INSPECTION_COMPLETED"]},
    {"status": "INSPECTION_COMPLETED", "remarks": "Inspection completed", "next": ["APPROVED", "REJECTED"]},
    {"status": "APPROVED", "remarks": "License approved", "renewal_period_days": 365, "next": ["REVOKED", "EXPIRED", "RENEWED"]},
    {"status": "EXPIRED", "remarks": "License expired", "next": ["RENEWED"]},
    {"status": "RENEWED", "remarks": "License renewed", "renewal_period_days": 365, "next": ["EXPIRED", "REVOKED"]},
]

# Status index for quick lookup
STATUS_INDEX = {item["status"]: item for item in status_flow}

# ---------------- MULTI-ACCOUNT MANAGEMENT ----------------
accounts = CONTRACT_ADDRESSES if CONTRACT_ADDRESSES and CONTRACT_ADDRESSES[0] else ['single_default_account']

# ---------------- MULTI-RPC NODE MANAGEMENT ----------------
class MultiRPCManager:
    """Manages multiple RPC nodes with health tracking and load balancing"""
    
    def __init__(self, rpc_urls):
        self.nodes = {}
        self.node_switch_count = 0
        self.NODE_TTL_MS = 10 * 60 * 1000  # 10 minutes
        self.NODE_BACKOFF_SECONDS = 20
        self.rpc_failures = 0
        
        # Initialize nodes with random latencies
        for url in rpc_urls:
            self.nodes[url] = {
                'url': url,
                'latency_ms': random.randint(80, 450),
                'consecutive_failures': 0,
                'last_failure_ts': 0,
                'success_count': 0,
                'error_count': 0,
                'last_updated': self.now_ms(),
                'active_requests': 0,
                'tokens_limit': 25 + random.randint(0, 10),
            }
        
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=50,
            max_retries=2
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        
        logger.info(f"🌐 MultiRPC initialized with {len(rpc_urls)} nodes")
    
    def now_ms(self):
        """Get current time in milliseconds"""
        return int(time.time() * 1000)
    
    def node_score(self, node):
        """Calculate node score (lower is better)"""
        return node['latency_ms'] + (node['consecutive_failures'] * 800)
    
    def is_node_healthy(self, node):
        """Check if node is healthy"""
        if node['consecutive_failures'] == 0:
            return True
        return (self.now_ms() - node['last_failure_ts']) > (self.NODE_BACKOFF_SECONDS * 1000)
    
    def choose_best_node(self):
        """Select the best available node"""
        pool_healthy = [node for node in self.nodes.values() if self.is_node_healthy(node)]
        pool = pool_healthy if pool_healthy else list(self.nodes.values())
        
        if not pool:
            return None
        if len(pool) == 1:
            return pool[0]
        
        # Select two random nodes and choose the better one
        a = random.choice(pool)
        b = random.choice(pool)
        tries = 0
        while b['url'] == a['url'] and tries < 5:
            b = random.choice(pool)
            tries += 1
        
        return a if self.node_score(a) <= self.node_score(b) else b
    
    def record_node_success(self, node, latency):
        """Record successful node operation"""
        alpha = 0.3
        node['latency_ms'] = int(alpha * latency + (1 - alpha) * node['latency_ms'])
        node['consecutive_failures'] = 0
        node['success_count'] += 1
        node['last_updated'] = self.now_ms()
    
    def record_node_failure(self, node):
        """Record node failure"""
        node['error_count'] += 1
        node['consecutive_failures'] += 1
        node['last_failure_ts'] = self.now_ms()
        node['last_updated'] = self.now_ms()
        self.rpc_failures += 1
    
    def simulate_rpc_ping(self, backend_url):
        """Simulate RPC ping through backend health endpoint"""
        node = self.choose_best_node()
        if not node:
            return
        
        self.node_switch_count += 1
        node['active_requests'] += 1
        
        start = self.now_ms()
        
        # Simulate latency
        overload = max(0, node['active_requests'] - node['tokens_limit'])
        simulated_latency = max(50, int(node['latency_ms'] * (0.7 + random.random() * 0.6) + overload * 15))
        
        try:
            # Call backend health endpoint
            response = self._session.get(
                f"{backend_url}/health/",
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            tps_monitor.incr()

            took = self.now_ms() - start + simulated_latency
            
            base_fail_chance = 0.02 + (node['consecutive_failures'] * 0.05) + (overload * 0.02)
            did_fail = (random.random() < base_fail_chance) or (response.status_code not in [200, 204])
            
            if did_fail:
                self.record_node_failure(node)
            else:
                self.record_node_success(node, took)
                
        except Exception as e:
            self.record_node_failure(node)
        finally:
            node['active_requests'] = max(0, node['active_requests'] - 1)

# Initialize MultiRPC Manager
rpc_manager = MultiRPCManager(RPC_URLS)

# ---------------- CACHE SIMULATION ----------------
class CacheManager:
    """Simple in-memory cache simulation"""
    
    def __init__(self, hit_rate=0.75):
        self.cache_store = {}
        self.CACHE_DEFAULT_TTL_MS = 60 * 1000  # 60 seconds for license data
        self.QR_CACHE_TTL_MS = 1800 * 1000  # 30 minutes for QR data 
        self.CACHE_HIT_RATE = hit_rate
        self.hits = 0
        self.misses = 0
    
    def now_ms(self):
        """Get current time in milliseconds"""
        return int(time.time() * 1000)
    
    def get(self, key):
        """Get from cache with TTL check"""
        entry = self.cache_store.get(key)
        
        if not entry:
            self.misses += 1
            return None
        
        # Check TTL
        if (self.now_ms() - entry['ts']) > entry['ttl']:
            del self.cache_store[key]
            self.misses += 1
            return None
        
        # Simulate cache hit rate
        if random.random() > self.CACHE_HIT_RATE:
            self.misses += 1
            return None
        
        self.hits += 1
        return entry['data']
    
    def set(self, key, data, ttl_ms=None):
        """Set cache entry with custom TTL"""
        self.cache_store[key] = {
            'data': data,
            'ts': self.now_ms(),
            'ttl': ttl_ms or self.CACHE_DEFAULT_TTL_MS
        }
    
    def delete(self, key):
        """Delete cache entry (matches Django cache.delete)"""
        if key in self.cache_store:
            del self.cache_store[key]
    
    # -------- LICENSE CACHE FUNCTIONS --------
    
    def get_license_basic_info(self, license_id):
        """Get license basic info from cache (matches Django cache key)"""
        cache_key = f"license_basic_info_{license_id}"
        return self.get(cache_key)
    
    def set_license_basic_info(self, license_id, data):
        """Cache license basic info with 30-min TTL (matches Django timeout=1800)"""
        cache_key = f"license_basic_info_{license_id}"
        self.set(cache_key, data, self.QR_CACHE_TTL_MS)  # 1800 seconds = 30 minutes
    
    def delete_license_basic_info(self, license_id):
        """Delete license basic info cache (matches Django cache.delete)"""
        cache_key = f"license_basic_info_{license_id}"
        self.delete(cache_key)
    
    # -------- QR CACHE FUNCTIONS  --------
    
    def get_qr_data(self, license_id):
        """Get QR data from cache (matches Django cache key)"""
        cache_key = f"license_qr_data_{license_id}"
        return self.get(cache_key)
    
    def set_qr_data(self, license_id, data):
        """Cache QR data with 30-min TTL (matches Django timeout=1800)"""
        cache_key = f"license_qr_data_{license_id}"
        self.set(cache_key, data, self.QR_CACHE_TTL_MS)  # 1800 seconds = 30 minutes
    
    def delete_qr_data(self, license_id):
        """Delete QR data cache (matches Django cache.delete)"""
        cache_key = f"license_qr_data_{license_id}"
        self.delete(cache_key)
    
    # -------- INVALIDATION --------
    
    def invalidate_license_cache(self, license_id):
        """
        Invalidate both license and QR cache for a license.
        Matches Django backend's cache invalidation on status update.
        """
        self.delete_license_basic_info(license_id)
        self.delete_qr_data(license_id)

# Initialize Cache
cache_manager = CacheManager()

# ---------------- METRICS COLLECTION ----------------
class TestMetrics:
    """Collects test metrics similar to k6"""
    
    def __init__(self):
        # Counters
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
        
        # Trends (we'll store response times for aggregation)
        self.create_times = []
        self.status_times = []
        self.verify_times = []
        self.qr_times = []
        self.count_times = []
        self.details_times = []
        self.rpc_ping_times = []
        
        # Error tracking
        self.errors = 0
        
    def add_create_time(self, duration):
        self.create_times.append(duration)
    
    def add_status_time(self, duration):
        self.status_times.append(duration)
    
    def add_verify_time(self, duration):
        self.verify_times.append(duration)
    
    def add_qr_time(self, duration):
        self.qr_times.append(duration)
    
    def add_count_time(self, duration):
        self.count_times.append(duration)
    
    def add_details_time(self, duration):
        self.details_times.append(duration)
    
    def add_rpc_ping_time(self, duration):
        self.rpc_ping_times.append(duration)
    
    def calculate_p95(self, times):
        if not times:
            return 0
        sorted_times = sorted(times)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[index]
    
    def calculate_avg(self, times):
        if not times:
            return 0
        return sum(times) / len(times)

metrics = TestMetrics()

# ---------------- TPS MEASUREMENT ----------------
class TPSMonitor:
    def __init__(self):
        self.total_requests = 0
        self.last_second_requests = 0
        self.current_tps = 0
        self.peak_tps = 0
        self.start_ts = time.time()

    def incr(self):
        """Count every request the moment it happens."""
        self.total_requests += 1
        self.last_second_requests += 1

    def sampler(self):
        """Runs every 1 sec to compute TPS."""
        while True:
            self.current_tps = self.last_second_requests
            self.peak_tps = max(self.peak_tps, self.current_tps)
            self.last_second_requests = 0
            gevent.sleep(1)

    def get_summary(self):
        run_time = max(1, int(time.time() - self.start_ts))
        avg_tps = self.total_requests / run_time
        return {
            "total_requests": self.total_requests,
            "current_tps": self.current_tps,
            "peak_tps": self.peak_tps,
            "avg_tps": round(avg_tps, 2),
        }


# Start TPS monitor
tps_monitor = TPSMonitor()
gevent.spawn(tps_monitor.sampler)

# ---------------- HELPER FUNCTIONS ----------------
def random_item(arr):
    return random.choice(arr) if arr else None

def random_int(min_val, max_val):
    return random.randint(min_val, max_val)

def async_sleep(seconds):
    gevent.sleep(seconds)

def safe_json(response):
    """Safely parse JSON response"""
    try:
        return response.json()
    except Exception as e:
        logger.debug(f"JSON parse error: {e}")
        return {}

def select_account():
    """Select random account from pool"""
    return random.choice(accounts)

def generate_application():
    """Generate random application data"""
    base = random_item(applicant_data)
    encrypted_aadhaar = random_item(ENCRYPTED_AADHAARS)
    license_number = f"RJ{random.choice(['SDDT','FDDT','SDST','FDST'])}-TEST-{random_int(1000,9999)}"

    
    return {
        **base,
        "licenseNumber": license_number,
        "aadhaarNumber": encrypted_aadhaar,
        "registeringAuthority": "Department of Agriculture",
        "registeringOfficeName": f"District Agri Office, {random_item(['Jaipur','Udaipur','Jodhpur','Kota'])}",
        "applicantPermanentAddress": f"H.No {random_int(1,100)}, {random_item(['Green','Royal','Sunrise'])} Colony",
        "firmAddress": f"Plot No {random_int(1,50)}, {random_item(['Mandi Road','Industrial Area','Agro Park'])}",
        "salePointAddress": f"Shop No {random_int(1,20)}, {random_item(['Krishi Market','Farmer Plaza','Agri Complex'])}",
        "saleStorageAddress": f"Warehouse {random_int(1,10)}, {random_item(['Outer Ring Road','Storage Zone','Logistics Park'])}",
    }

def log_message(user, msg):
    """Log structured message similar to k6"""
    vu_id = getattr(user, 'vu_id', 0)
    iter_num = getattr(user, 'iter_num', 0)
    logger.info(f"[VU {vu_id} | ITER {iter_num}] {msg}")

# ---------------- REQUEST HANDLERS WITH METRICS ----------------
def handle_create_license(user, payload):
    """Handle license creation"""
    start_time = time.time()
    account = select_account()
    if user.iter_num % 50 == 0:
        log_message(user, f"INFO 🎲 Using random account from pool: {account}")
    
    try:
        with user.client.post(
            "/license/create/", 
            json=payload, 
            headers=JSON_HEADERS, 
            catch_response=True, 
            name="/license/create",
            timeout=120
        ) as response:
            duration = (time.time() - start_time) * 1000  # Convert to ms
            metrics.add_create_time(duration)
            
            if response.status_code in [200, 201, 202]:
                metrics.create_ok += 1
                response.success()
                tps_monitor.incr()

                # Parse and cache response
                body = safe_json(response)
                license_id = None
                
                # Extract license_id from response
                if body and 'data' in body:
                    # Check for transaction_hash (new license) or licenseId (if present)
                    if 'transaction_hash' in body['data']:
                        log_message(user, f"🟢 POST /license/create → {response.status_code} ({int(duration)} ms) • tx: {body['data']['transaction_hash'][:10]}...")
                        # License ID will need to be fetched later
                        return None
                    elif 'license_id' in body['data']:
                        license_id = body['data']['license_id']
                
                if license_id:
                    log_message(user, f"🟢 POST /license/create → {response.status_code} ({int(duration)} ms) • licenseId: {license_id}")
                else:
                    log_message(user, f"🟢 POST /license/create → {response.status_code} ({int(duration)} ms)")
                
                return license_id
            else:
                metrics.create_fail += 1
                metrics.errors += 1
                body_snippet = response.text[:400] if response.text else '[Empty response]'
                log_message(user, f"❌ License Creation Failed:\n• Status: {response.status_code}\n• Response: {body_snippet}")
                response.failure(f"Status: {response.status_code}")
                return None
    except Exception as e:
        metrics.errors += 1
        log_message(user, f"❌ POST /license/create request error: {str(e)}")
        return None

def handle_get_license_count(user):
    """Handle license count retrieval"""
    start_time = time.time()
    
    try:
        with user.client.get(
            "/license/count/", 
            catch_response=True, 
            name="/license/count",
            timeout=60
        ) as response:
            duration = (time.time() - start_time) * 1000
            metrics.add_count_time(duration)
            
            if response.status_code == 200:
                metrics.count_ok += 1
                response.success()
                tps_monitor.incr()

                body = safe_json(response)
                total = 0
                if body and 'data' in body and 'total_licenses' in body['data']:
                    total = int(body['data']['total_licenses'])
                elif body and 'total_licenses' in body:
                    total = int(body['total_licenses'])
                
                return total
            else:
                metrics.count_fail += 1
                log_message(user, f"❌ License count failed: {response.status_code}")
                response.failure(f"Status: {response.status_code}")
                return 0
    except Exception as e:
        metrics.errors += 1
        log_message(user, f"❌ GET /license/count request error: {str(e)}")
        return 0

def handle_get_license_details(user, license_id):
    """Handle license details retrieval with cache (MATCHING DJANGO BACKEND)"""
    # Try cache first 
    cached_data = cache_manager.get_license_basic_info(license_id)
    if cached_data:
        log_message(user, f"INFO 💾 Cache hit for license basic info {license_id}")
        return cached_data
    
  
    log_message(user, f"INFO 🔍 Cache miss for license {license_id}, reading from backend")
    start_time = time.time()
    
    try:
        with user.client.get(
            f"/license/info/{license_id}/", 
            catch_response=True, 
            name="/license/info/license_id",
            timeout=60
        ) as response:
            duration = (time.time() - start_time) * 1000
            metrics.add_details_time(duration)
            
            if response.status_code == 200:
                metrics.details_ok += 1
                response.success()
                tps_monitor.incr()

                body = safe_json(response)
           
                license_data = body.get('data', {})
                
                # Cache with 30-min TTL 
                if license_data and 'status' in license_data:
                    cache_manager.set_license_basic_info(license_id, license_data)
                    log_message(user, f"INFO 💾 Cached license basic info {license_id} with 30-min TTL")
                
                return license_data
            elif response.status_code == 404:
                log_message(user, f"WARNING ⚠️ Not Found: /license/info/{license_id}/")
                response.success()
                return None
            else:
                metrics.details_fail += 1
                metrics.errors += 1
                log_message(user, f"❌ GET /license/info/{license_id}/ -> {response.status_code}")
                response.failure(f"Status: {response.status_code}")
                return None
    except Exception as e:
        metrics.errors += 1
        log_message(user, f"❌ GET /license/info/{license_id} request error: {str(e)}")
        return None

def handle_get_qr(user, license_id):
    """Handle QR code retrieval with cache (MATCHING DJANGO BACKEND)"""
    # Try cache first 
    cached_qr = cache_manager.get_qr_data(license_id)
    if cached_qr:
        log_message(user, f"INFO 💾 Cache hit for QR data {license_id}")
        metrics.qr_ok += 1
        return cached_qr
    
    # Cache miss
    log_message(user, f"INFO 🔍 Cache miss for QR data {license_id}")
    start_time = time.time()
    
    try:
        with user.client.get(
            f"/license/qr/{license_id}/", 
            catch_response=True, 
            name="/license/qr/license_id",
            timeout=60
        ) as response:
            duration = (time.time() - start_time) * 1000
            metrics.add_qr_time(duration)
            
            if response.status_code in [200, 202]:
                metrics.qr_ok += 1
                response.success()
                tps_monitor.incr()

                body = safe_json(response)
              
                qr_data = body.get('data', {})
                
                # Cache with 30-min TTL 
                if qr_data and 'license_number' in qr_data:
                    cache_manager.set_qr_data(license_id, qr_data)
                    log_message(user, f"📦 QR data retrieved and cached for license {license_id} with 30-min TTL")
                
                return qr_data
            else:
                metrics.qr_fail += 1
                metrics.errors += 1
                log_message(user, f"❌ QR fetch failed for {license_id}: {response.status_code}")
                response.failure(f"Status: {response.status_code}")
                return None
    except Exception as e:
        metrics.errors += 1
        log_message(user, f"❌ GET /license/qr/{license_id} error: {str(e)}")
        return None

def handle_update_status(user, payload, license_id):
    """Handle status update with retry logic and cache invalidation (MATCHING DJANGO BACKEND)"""
    account = select_account()
    if user.iter_num % 250 == 0:
        log_message(user, f"INFO 🎲 Using random account from pool: {account}")
    
    log_message(user, f"📋 License {license_id}: {payload.get('current_status', 'UNKNOWN')} → {payload['status']} (by {payload['officer_name']})")
    
    # Retry logic
    for attempt in range(3):
        start_time = time.time()
        
        try:
            with user.client.post(
                "/license/update-status/", 
                json=payload, 
                headers=JSON_HEADERS, 
                catch_response=True, 
                name="/license/update-status",
                timeout=120
            ) as response:
                duration = (time.time() - start_time) * 1000
                metrics.add_status_time(duration)
                
                # Backend returns 202 for successful status update or 200 for no change
                if response.status_code in [200, 202]:
                    body = safe_json(response)
                    
                    # Check if it's a "no change" response
                    if body.get('data', {}).get('status') == 'no_change':
                        metrics.status_ok += 1
                        response.success()
                        log_message(user, f"ℹ️ No change: License {license_id} already in status {payload['status']}")
                        return False
                    
                    metrics.status_ok += 1
                    response.success()
                    tps_monitor.incr()

                    # Invalidate cache on successful status update
                    cache_manager.invalidate_license_cache(license_id)
                    
                    log_message(user, f"✅ Status update success for {license_id}: {payload.get('current_status', 'UNKNOWN')} → {payload['status']} (http {response.status_code})")
                    return True
                else:
                    body_text = (response.text or "").lower()
                    
                    # Business logic errors - don't retry
                    if response.status_code == 400:
                        metrics.status_fail += 1
                        log_message(user, f"ℹ️ Business logic prevented update: {response.text[:200]}")
                        response.success()
                        return False
                    
                    # Transient errors - retry
                    if "gas" in body_text or "nonce" in body_text or response.status_code == 429:
                        delay = (2 ** attempt) * random_int(1, 4)
                        log_message(user, f"⚠️ Blockchain error for {license_id} (attempt {attempt+1}) - retrying in {delay}s. status={response.status_code}")
                        async_sleep(delay)
                        continue
                    
                    # Other errors
                    metrics.status_fail += 1
                    metrics.errors += 1
                    log_message(user, f"❌ Update failed for {license_id}: {response.status_code} • {response.text[:200]}")
                    response.failure(f"Status: {response.status_code}")
                    break
        except Exception as e:
            metrics.errors += 1
            log_message(user, f"❌ POST /license/update-status request error: {str(e)}")
            async_sleep((2 ** attempt) * random_int(1, 3))
            continue
    
    return False

def handle_verify_license(user, payload):
    """Handle license verification"""
    start_time = time.time()
    
    try:
        with user.client.post(
            "/license/verify/", 
            json=payload, 
            headers=JSON_HEADERS, 
            catch_response=True, 
            name="/license/verify",
            timeout=60
        ) as response:
            duration = (time.time() - start_time) * 1000
            metrics.add_verify_time(duration)
            
            if response.status_code in [200, 202]:
                metrics.verify_ok += 1
                response.success()
                tps_monitor.incr()
                log_message(user, f"✅ License verified successfully ({int(duration)}ms)")
                return True
            else:
                metrics.verify_fail += 1
                metrics.errors += 1
                log_message(user, f"❌ Verification failed: {response.status_code} • {response.text[:200]}")
                response.failure(f"Status: {response.status_code}")
                return False
    except Exception as e:
        metrics.errors += 1
        log_message(user, f"❌ POST /license/verify error: {str(e)}")
        return False

def get_next_valid_status(current_status):
    """Get next valid status from the workflow"""
    status_info = STATUS_INDEX.get(current_status)
    if not status_info or not status_info.get('next'):
        return None
    
    # Return a random next valid status
    return random.choice(status_info['next'])

# ---------------- LOCUST USER CLASS ----------------
class SeedLicensingUser(HttpUser):
    host = BASE_URL
    wait_time = between(1, 3)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vu_id = random.randint(1, 10000)
        self.iter_num = 0
    
    @task(3)
    def citizen_submit_license(self):
        """Citizen submits a new license application"""
        self.iter_num += 1
        
        # Periodically refresh RPC stats
        if self.iter_num % 4 == 0:
            rpc_manager.simulate_rpc_ping(self.host)
        
        payload = generate_application()
        license_id = handle_create_license(self, payload)
        
        async_sleep(random_int(2, 4))
    
    @task(7)
    def officer_workflow(self):
        """Officer performs license workflow updates"""
        self.iter_num += 1
        
        # Periodically refresh RPC stats
        if self.iter_num % 4 == 0:
            rpc_manager.simulate_rpc_ping(self.host)
        
        # Get total licenses
        total_licenses = handle_get_license_count(self)
        if total_licenses < 1:
            log_message(self, "⚠️ No licenses exist")
            async_sleep(1)
            return
        
        # Select license ID
        license_id = random_int(1, total_licenses)
        
        # Try to use a cached license ID (70% chance)
        if random.random() < 0.7:
            cached_keys = list(cache_manager.cache_store.keys())
            license_keys = [k for k in cached_keys if k.startswith('license_basic_info_')]
            if license_keys:
                key = random.choice(license_keys)
                try:
                    cached_id = int(key.split('_')[-1])
                    if 1 <= cached_id <= total_licenses:
                        license_id = cached_id
                except ValueError:
                    pass
        
        # Get license details (with cache)
        license_data = handle_get_license_details(self, license_id)
        if not license_data or 'status' not in license_data:
            log_message(self, f"⚠️ Invalid license data for ID {license_id}")
            async_sleep(0.5)
            return
        
        # Status is returned as string from backend (e.g., "APPROVED")
        current_status = license_data['status']
        
        # ========== SCENARIO 1: License is already APPROVED ==========
        if current_status == 'APPROVED':
            log_message(self, f"🎯 License {license_id} is already APPROVED. Performing QR fetch and verification...")
            
            # Get QR code with cache 
            qr_data = handle_get_qr(self, license_id)
            
            # Debug: Log the QR data structure
            if qr_data:
                log_message(self, f"DEBUG 🔍 QR data keys: {list(qr_data.keys())}")
            else:
                log_message(self, f"⚠️ No QR data returned for license {license_id}")
                async_sleep(random_int(1, 3))
                return
            
            # Check various possible field names in QR response
            license_number = qr_data.get('license_number') or qr_data.get('licenseNumber') or qr_data.get('license_id')
            verification_hash = qr_data.get('verification_hash') or qr_data.get('verificationHash') or qr_data.get('hash')
            
            if license_number and verification_hash:
                # Verify license
                verify_payload = {
                    "license_number": str(license_number),
                    "expected_hash": str(verification_hash)
                }
                log_message(self, f"DEBUG 🔍 Verification payload: license_number={license_number}, hash={verification_hash[:20]}...")
                verify_success = handle_verify_license(self, verify_payload)
                if verify_success:
                    log_message(self, f"✅ Approved license {license_id} verified successfully")
                else:
                    log_message(self, f"❌ Verification failed for approved license {license_id}")
            else:
                log_message(self, f"⚠️ Approved license {license_id} has incomplete QR data - license_number: {license_number}, hash: {verification_hash}")
            
            async_sleep(random_int(1, 3))
            return
        
        # ========== SCENARIO 2: License is in other final state ==========
        if current_status in ['REJECTED', 'REVOKED']:
            log_message(self, f"⏭️ Skipping license {license_id} in final state: {current_status}")
            async_sleep(0.2)
            return
        
        # ========== SCENARIO 3: Normal workflow to move to next status ==========
        next_status = get_next_valid_status(current_status)
        
        if not next_status:
            log_message(self, f"⚠️ No valid next status for {current_status} (id {license_id})")
            async_sleep(0.2)
            return
        
        # Get status info for the next status
        next_status_info = STATUS_INDEX.get(next_status)
        if not next_status_info:
            log_message(self, f"⚠️ Status info not found for {next_status}")
            async_sleep(0.2)
            return
        
        officer = random_item(officer_data)
        
        # Prepare payload with correct field names (snake_case)
        payload = {
            "license_id": license_id,
            "status": next_status,
            "officer_name": officer['name'],
            "role": officer['role'],
            "remarks": f"{next_status_info['remarks']} by {officer['name']} at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "current_status": current_status
        }
        
        # Add renewal_period_days if required
        if next_status in ['APPROVED', 'RENEWED']:
            payload['renewal_period_days'] = next_status_info.get('renewal_period_days', 365)
        
        # Update status
        update_success = handle_update_status(self, payload, license_id)
        
        # ========== SCENARIO 4: If we just approved a license ==========
        if update_success and next_status == 'APPROVED':
            log_message(self, f"🎉🎉🎉 License {license_id} JUST APPROVED! Fetching QR and verifying...")
            async_sleep(random.uniform(0.5, 1.5))
            
            # Get QR code 
            qr_data = handle_get_qr(self, license_id)
            
            if qr_data:
                log_message(self, f"DEBUG 🔍 Newly approved QR data keys: {list(qr_data.keys())}")
            else:
                log_message(self, f"⚠️ No QR data returned for newly approved license {license_id}")
                async_sleep(random_int(1, 3))
                return
            
            # Check various possible field names
            license_number = qr_data.get('license_number') or qr_data.get('licenseNumber') or qr_data.get('license_id')
            verification_hash = qr_data.get('verification_hash') or qr_data.get('verificationHash') or qr_data.get('hash')
            
            if license_number and verification_hash:
                # Verify license
                verify_payload = {
                    "license_number": str(license_number),
                    "expected_hash": str(verification_hash)
                }
                log_message(self, f"DEBUG 🔍 Newly approved verification payload: license_number={license_number}, hash={verification_hash[:20]}...")
                verify_success = handle_verify_license(self, verify_payload)
                if verify_success:
                    log_message(self, f"✅✅✅ Newly approved license {license_id} verified successfully!")
                else:
                    log_message(self, f"❌ Verification failed for newly approved license {license_id}")
            else:
                log_message(self, f"⚠️ Newly approved license {license_id} has incomplete QR data - license_number: {license_number}, hash: {verification_hash}")
        
        # Occasionally refresh RPC stats
        if self.iter_num % 3 == 0:
            rpc_manager.simulate_rpc_ping(self.host)
        
        async_sleep(random_int(1, 3))

# ---------------- LOCUST EVENT HANDLERS ----------------
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("🚀 Starting Rajasthan Seed Licensing Stress Test")
    logger.info(f"🌐 Backend URL: {BASE_URL}")
    logger.info(f"🔗 RPC Nodes: {RPC_URLS}")
    logger.info(f"👥 Using {len(accounts)} blockchain account(s)")
    
    # Initial API connectivity check
    try:
        response = requests.get(f"{BASE_URL}/owner/", timeout=10)
        logger.info(f"API connectivity check: {response.status_code}")
        if response.status_code != 200:
            logger.error("❌ Backend not reachable — check Django + blockchain nodes.")
        else:
            logger.info("✅ Backend reachable. Proceeding...")
    except Exception as e:
        logger.error(f"❌ Error occurred while checking API connectivity: {e}")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("🧹 Test completed")
    
    # Print final metrics
    logger.info("📊 ======= TEST COMPLETE =======")
    logger.info(f"✅ License Creation: {metrics.create_ok} successful, {metrics.create_fail} failed")
    logger.info(f"✅ Status Updates: {metrics.status_ok} successful, {metrics.status_fail} failed")
    logger.info(f"✅ QR Fetches: {metrics.qr_ok} successful, {metrics.qr_fail} failed")
    logger.info(f"✅ Verifications: {metrics.verify_ok} successful, {metrics.verify_fail} failed")
    logger.info(f"✅ License Count: {metrics.count_ok} successful, {metrics.count_fail} failed")
    logger.info(f"✅ License Details: {metrics.details_ok} successful, {metrics.details_fail} failed")
    
    # Calculate and display response time statistics
    if metrics.create_times:
        logger.info(f"⏱️  Create Avg: {metrics.calculate_avg(metrics.create_times):.2f}ms, P95: {metrics.calculate_p95(metrics.create_times):.2f}ms")
    if metrics.status_times:
        logger.info(f"⏱️  Status Avg: {metrics.calculate_avg(metrics.status_times):.2f}ms, P95: {metrics.calculate_p95(metrics.status_times):.2f}ms")
   
    # Cache statistics
    total_cache_ops = cache_manager.hits + cache_manager.misses
    hit_rate = (cache_manager.hits / total_cache_ops * 100) if total_cache_ops > 0 else 0
    logger.info(f"💾 Cache Hits: {cache_manager.hits}, Misses: {cache_manager.misses}")
    logger.info(f"💾 Cache Hit Rate: {hit_rate:.2f}%")
    
    # RPC statistics
    logger.info(f"🔗 RPC Failures: {rpc_manager.rpc_failures}")
    
    # Total errors
    logger.info(f"❌ Total Errors: {metrics.errors}")
    
    # TPS Summary
    summary = tps_monitor.get_summary()
    logger.info("\n==================== TPS SUMMARY ====================")
    logger.info(f"Total Requests:   {summary['total_requests']}")
    logger.info(f"Average TPS:      {summary['avg_tps']}")
    logger.info(f"Peak TPS:         {summary['peak_tps']}")
    logger.info(f"Last Reported TPS:{summary['current_tps']}")
    logger.info("=====================================================\n")
    
    # Cleanup
    if hasattr(rpc_manager, '_session'):
        rpc_manager._session.close()
