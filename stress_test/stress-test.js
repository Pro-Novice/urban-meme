import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend, Counter, Gauge } from 'k6/metrics';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.1.0/index.js';

// ---------------- CONFIG ----------------
export const options = {
  stages: [
    { duration: '10s', target: 100 },
    { duration: '10s', target: 300 },
    { duration: '20s', target: 400 },
    { duration: '20s', target: 500 },
    { duration: '20s', target: 600 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<=0.5'],
    http_req_duration: ['p(95)<90000', 'avg<60000'],
  },
  discardResponseBodies: false,
};

// ---------------- ENV ----------------
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000/api/blockchain';
const RPC_URLS = (__ENV.RPC_URLS || 'http://host.docker.internal:8545').split(',').map(s => s.trim()).filter(Boolean);
const MULTI_ACCOUNTS = (__ENV.CONTRACT_ADDRESSES || '').split(',').map(s => s.trim()).filter(Boolean);
const JSON_HEADERS = { headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' } };

// ---------------- METRICS ----------------
export let requestCounter = new Counter('http_reqs_total');
export let createTrend = new Trend('License_Create_Duration');
export let statusTrend = new Trend('Status_Update_Duration');
export let verifyTrend = new Trend('Verify_Duration');
export let qrTrend = new Trend('QR_Fetch_Duration');
export let countTrend = new Trend('License_Count_Duration');
export let detailsTrend = new Trend('License_Details_Duration');
export let rpcPingTrend = new Trend('RPC_Ping_Duration');
export let rpcFailures = new Counter('rpc_failures');
export let cacheHitCounter = new Counter('cache_hits');
export let cacheMissCounter = new Counter('cache_misses');
export let nodeSwitchGauge = new Gauge('node_switch_count');
export let errorRate = new Counter('errors');

// ---------------- HELPERS ----------------
function nowMs(){ return Date.now(); }
function randInt(min, max){ return Math.floor(Math.random() * (max - min + 1)) + min; }
function randItem(arr){ return arr[Math.floor(Math.random() * arr.length)]; }

function log(msg){
  // concise structured log line
  console.log(`[VU ${__VU} | ITER ${__ITER}] ${msg}`);
}

function safeJson(res){
  try {
    // k6 Response has .json() helper
    if (typeof res.json === 'function') return res.json();
    return JSON.parse(res.body || '{}');
  } catch (e) {
    const snippet = typeof res.body === 'string' ? res.body.substring(0, 200) : String(res.body || '');
    log(`❌ JSON parse error: ${e.message} — body: ${snippet}`);
    return {};
  }
}

// ---------------- SHARED DATA ----------------
const encryptedAadhaars = new SharedArray('encryptedAadhaars', function(){
  try {
    return JSON.parse(open('encrypted_aadhaar.json'));
  } catch (e) {
    console.error('⚠️ Failed to load encrypted_aadhaar.json:', e);
    return ['default_encrypted_aadhaar'];
  }
});
function getEncryptedAadhaar(){ return randItem(encryptedAadhaars); }

// ---------------- STATIC TEST DATA ----------------
const applicantData = new SharedArray('applicants', () => [
  {
    licenseCategory: 'SEED',
    licenseLevel: 'DISTRICT',
    applicantName: 'Ravi Kumar',
    firmName: 'Ravi Agro Traders',
    firmType: 'Partnership',
    cropName: 'Wheat',
    cropVariety: 'HD2967',
    isSeedSelfProduced: false,
    productionCompany: 'Sharma Seeds Pvt Ltd',
  },
  {
    licenseCategory: 'FERTILIZER',
    licenseLevel: 'STATE',
    applicantName: 'Priya Sharma',
    firmName: 'Green Earth Fertilizers',
    firmType: 'Private Limited',
    cropName: 'Rice',
    cropVariety: 'Basmati',
    isSeedSelfProduced: false,
    productionCompany: 'AgroTech Ltd',
  },
]);

const officerData = [
  { name: 'Shrawan', role: 'AGRICULTURE_OFFICER' },
  { name: 'Rajesh', role: 'JOINT_DIRECTOR' },
  { name: 'Meena', role: 'DEPUTY_DIRECTOR' },
  { name: 'Arun', role: 'ASSISTANT_DIRECTOR' },
];

const statusFlow = [
  { status: 'SUBMITTED', remarks: 'Application submitted' },
  { status: 'UNDER_REVIEW', remarks: 'Application under review' },
  { status: 'DOCUMENTS_VERIFIED', remarks: 'Documents verified' },
  { status: 'INSPECTION_SCHEDULED', remarks: 'Inspection scheduled' },
  { status: 'INSPECTION_COMPLETED', remarks: 'Inspection completed' },
  { status: 'APPROVED', remarks: 'License approved', renewalPeriodDays: 365 },
];

const stats = {
  create_ok: 0,
  create_fail: 0,
  status_ok: 0,
  status_fail: 0,
  qr_ok: 0,
  qr_fail: 0,
  verify_ok: 0,
  verify_fail: 0,
};
// ---------------- MULTI-ACCOUNT ----------------
const accounts = MULTI_ACCOUNTS.length ? MULTI_ACCOUNTS : ['single_default_account'];
function selectAccount(){
  return randItem(accounts);
}

// ---------------- NODE / MULTI-RPC SIMULATION ----------------
// Keep node structure similar to Python MultiRPC
const NODE_TTL_MS = 10 * 60 * 1000; // 10 minutes TTL for node "session"
const NODE_BACKOFF_SECONDS = 20;
let nodes = {};
let nodeSwitchCount = 0;

function initNodes(urls){
  urls.forEach(url => {
    nodes[url] = {
      url,
      latencyMs: randInt(80, 450),
      consecutiveFailures: 0,
      lastFailureTs: 0,
      successCount: 0,
      errorCount: 0,
      lastUpdated: nowMs(),
      activeRequests: 0,
      tokensLimit: 25 + randInt(0, 10),
    };
  });
}
if(RPC_URLS.length === 0) initNodes(['http://localhost:8545']);
else initNodes(RPC_URLS);

function nodeScore(node){
  return node.latencyMs + (node.consecutiveFailures * 800);
}
function isNodeHealthy(node){
  if(node.consecutiveFailures === 0) return true;
  return (nowMs() - node.lastFailureTs) > (NODE_BACKOFF_SECONDS * 1000);
}
function chooseBestNode(){
  const poolHealthy = Object.values(nodes).filter(isNodeHealthy);
  const pool = poolHealthy.length ? poolHealthy : Object.values(nodes);
  if(pool.length === 0) return null;
  if(pool.length === 1) return pool[0];
  const a = randItem(pool);
  let b = randItem(pool);
  let tries = 0;
  while(b.url === a.url && tries++ < 5) b = randItem(pool);
  return nodeScore(a) <= nodeScore(b) ? a : b;
}

function recordNodeSuccess(node, latency){
  const alpha = 0.3;
  node.latencyMs = Math.round(alpha * latency + (1 - alpha) * node.latencyMs);
  node.consecutiveFailures = 0;
  node.successCount += 1;
  node.lastUpdated = nowMs();
}
function recordNodeFailure(node){
  node.errorCount += 1;
  node.consecutiveFailures += 1;
  node.lastFailureTs = nowMs();
  node.lastUpdated = nowMs();
  rpcFailures.add(1);
}

// ---------------- CACHE SIMULATION ----------------
let cacheStore = {};
const CACHE_DEFAULT_TTL_MS = 60 * 1000; // 60s
const CACHE_HIT_RATE = 0.75;

function cacheGet(licenseId){
  const key = `license:${licenseId}`;
  const entry = cacheStore[key];
  if(!entry){
    cacheMissCounter.add(1);
    return null;
  }
  if((nowMs() - entry.ts) > entry.ttl){
    delete cacheStore[key];
    cacheMissCounter.add(1);
    return null;
  }
  if(Math.random() > CACHE_HIT_RATE){
    cacheMissCounter.add(1);
    return null;
  }
  cacheHitCounter.add(1);
  return entry.data;
}
function cacheSet(licenseId, data, ttlMs){
  const key = `license:${licenseId}`;
  cacheStore[key] = { data, ts: nowMs(), ttl: ttlMs || CACHE_DEFAULT_TTL_MS };
}
function cacheInvalidate(licenseId){
  const key = `license:${licenseId}`;
  if(cacheStore[key]) delete cacheStore[key];
  // visible log for debugging
  log(`INFO Cache invalidated for license ${licenseId}`);
}

// ---------------- RPC PING SIMULATION (via backend health endpoint) ----------------
function simulatedRpcPing(){
  const node = chooseBestNode();
  if(!node) return;
  nodeSwitchCount++;
  nodeSwitchGauge.add(nodeSwitchCount);

  node.activeRequests++;
  const start = nowMs();

  const overload = Math.max(0, node.activeRequests - node.tokensLimit);
  const simulatedLatency = Math.max(50, Math.round(node.latencyMs * (0.7 + Math.random() * 0.6) + overload * 15));
  const baseFailChance = 0.02 + (node.consecutiveFailures * 0.05) + (overload * 0.02);

  let res = null;
  try {
    // call backend health endpoint (the backend will check blockchain node connectivity)
    res = http.get(`${BASE_URL}/health/`, { timeout: '30s' });
  } catch (e) {
    recordNodeFailure(node);
    node.activeRequests = Math.max(0, node.activeRequests - 1);
    return;
  }

  const took = nowMs() - start + simulatedLatency;
  rpcPingTrend.add(took);

  const didFail = (Math.random() < baseFailChance) || (res.status !== 200 && res.status !== 204);
  if(didFail) recordNodeFailure(node);
  else recordNodeSuccess(node, took);

  node.activeRequests = Math.max(0, node.activeRequests - 1);
}

// ---------------- APPLICATION HELPERS ----------------
function generateApplication(){
  const base = randItem(applicantData);
  return {
    ...base,
    aadhaarNumber: getEncryptedAadhaar(),
    registeringAuthority: 'Department of Agriculture',
    registeringOfficeName: `District Agri Office, ${randItem(['Jaipur','Udaipur','Jodhpur','Kota'])}`,
    applicantPermanentAddress: `H.No ${randInt(1,100)}, ${randItem(['Green','Royal','Sunrise'])} Colony`,
    firmAddress: `Plot No ${randInt(1,50)}, ${randItem(['Mandi Road','Industrial Area','Agro Park'])}`,
    salePointAddress: `Shop No ${randInt(1,20)}, ${randItem(['Krishi Market','Farmer Plaza','Agri Complex'])}`,
    saleStorageAddress: `Warehouse ${randInt(1,10)}, ${randItem(['Outer Ring Road','Storage Zone','Logistics Park'])}`,
  };
}

// ---------------- SETUP ----------------
export function setup() {
  console.log('🚀 Starting Rajasthan Seed Licensing Stress Test');
  console.log(`🌐 Backend URL: ${BASE_URL}`)
  console.log(`🔗 RPC Nodes: ${Object.keys(nodes).join(', ')}`);
  console.log(`👥 Using ${accounts.length} blockchain account(s)`)
  // initial API connectivity check;
  try {
    const res = http.get(`${BASE_URL}/owner/`);
    console.log(`API connectivity check: ${res.status}`);
    if (res.status !== 200) {
      console.error('❌ Backend not reachable — check Django + blockchain nodes.');
    } else {
      console.log('✅ Backend reachable. Proceeding...');
    }
  } catch (error) {
    console.error('❌ Error occurred while checking API connectivity:', error);
  }
}

// ---------------- MAIN FLOW ----------------
export default function(){
  // periodically refresh node stats
  if(__ITER % 4 === 0) simulatedRpcPing();

  const isCitizen = randInt(0, 1) === 0;

  if(isCitizen){
    group('Citizen: License Creation', function(){
      const payload = generateApplication();
      const acct = selectAccount();
      if(__ITER % 50 === 0) log(`INFO 🎲 Using random account from pool: ${acct}`);

      const start = nowMs();
      let res = null;
      try {
        res = http.post(`${BASE_URL}/license/create/`, JSON.stringify(payload), JSON_HEADERS, { timeout: '120s' });
      } catch (e) {
        errorRate.add(1);
        log(`❌ POST /license/create request error: ${e.message}`);
        sleep(randInt(1,3));
        return;
      }

      const dur = nowMs() - start;
      createTrend.add(dur);
      requestCounter.add(1);

      const ok = check(res, { 'Application submitted successfully': (r) => [200, 201, 202].includes(r.status) });
      if ([200, 201, 202].includes(res.status)) stats.create_ok++;
      else {
        stats.create_fail++;
        log(`❌ License Creation Failed:
          • Status: ${res.status}
          • Response Body: ${res.body ? res.body.substring(0, 400) : '[Empty response]'}`);
      }
      if (ok) {
          stats.create_ok++;
      } else {
          stats.create_fail++;
      }
      if(ok){
        // parse, store potential returned license id to cache
        const body = safeJson(res);
        // backend returns wrapped data sometimes: { data: {...} } or directly { transaction_hash:... }
        const licenseId = (body && body.data && body.data.licenseId) || (body && body.licenseId) || null;
        if(licenseId){
          cacheSet(licenseId, body.data || body, (15 + randInt(0,30)) * 1000);
          log(`🟢 POST /license/create → ${res.status} (${dur} ms) • licenseId: ${licenseId}`);
        } else {
          log(`🟢 POST /license/create → ${res.status} (${dur} ms)`);
        }
      } else {
        errorRate.add(1);
      }

      sleep(randInt(2,4));
    });
    return;
  }

  // Officer workflow
  group('Officer: License Workflow', function(){
    const startCount = nowMs();
    let countRes = null;
    try {
      countRes = http.get(`${BASE_URL}/license/count/`, { timeout: '60s' });
    } catch (e) {
      errorRate.add(1);
      log(`❌ GET /license/count request error: ${e.message}`);
      sleep(1);
      return;
    }

    const countDur = nowMs() - startCount;
    countTrend.add(countDur);
    requestCounter.add(1);
    
    check(countRes, { 'License count retrieved': (r) => r.status === 200 });
    
    if (countRes.status !== 200) {
      log(`❌ License count failed: ${countRes.status}`);
      sleep(1);
      return;
    }
    
    const countJson = safeJson(countRes);
    
   
    const total = Number(
      countJson?.data?.total_licenses ||
      countJson?.total_licenses ||
      countJson?.count ||  // Try this as fallback
      0
    );

    if (!total || total < 1) {
      log("⚠️ No licenses exist");
      sleep(1);
      return;
    }

    let licenseId = randInt(1, total);

    const cachedKeys = Object.keys(cacheStore);
    if(cachedKeys.length > 0 && Math.random() < 0.7){
      const k = randItem(cachedKeys); // format license:<id>
      const parts = k.split(':');
      const parsedId = Number(parts[1]);
      if (!isNaN(parsedId) && parsedId > 0 && parsedId <= total) {
        licenseId = parsedId;
      }
    }

    // Ensure licenseId is a valid number
    if (!Number.isInteger(licenseId) || licenseId < 1 || licenseId > total) {
      log(`⚠️ Invalid licenseId generated: ${licenseId}, using random`);
      licenseId = randInt(1, total);
    }

    // Try from in-memory cache first
    let licenseData = cacheGet(licenseId);
    if(licenseData){
      log(`INFO Cache hit for license ${licenseId}`);
    } else {
      // fetch details and set cache
      const startDetails = nowMs();
      let detailsRes = null;
      try {
        detailsRes = http.get(`${BASE_URL}/license/info/${licenseId}/`, { timeout: '60s' });
      } catch (e) {
        errorRate.add(1);
        log(`❌ GET /license/info/${licenseId} request error: ${e.message}`);
        sleep(0.5);
        return;
      }
      const dDur = nowMs() - startDetails;
      detailsTrend.add(dDur);
      requestCounter.add(1);
      
      check(detailsRes, { 'License details retrieved': (r) => r.status === 200 });
      
      if(detailsRes.status !== 200){
        // If Not Found - just skip
        if(detailsRes.status === 404){
          log(`WARNING Not Found: /license/info/${licenseId}/`);
        } else {
          errorRate.add(1);
          log(`❌ GET /license/info/${licenseId}/ -> ${detailsRes.status}`);
        }
        sleep(0.5);
        return;
      }

      const detailsBody = safeJson(detailsRes);
      licenseData = detailsBody.data || detailsBody;
      
      // Only cache if we have valid data
      if (licenseData && licenseData.status) {
        cacheSet(licenseId, licenseData, (30 + randInt(0, 90)) * 1000);
        log(`INFO Cache miss for license ${licenseId}, reading from backend and set TTL`);
      }
    }

    if(!licenseData || !licenseData.status){
      log(`⚠️ Invalid license data for ID ${licenseId}`);
      sleep(0.5);
      return;
    }

    if(['APPROVED','REJECTED','REVOKED','EXPIRED'].includes(licenseData.status)){
      log(`⏭️ Skipping license ${licenseId} in final state: ${licenseData.status}`);
      sleep(0.2);
      return;
    }
   
    const currentIdx = statusFlow.findIndex(s => s.status === licenseData.status);
    if(currentIdx === -1 || currentIdx >= statusFlow.length - 1){
      log(`⚠️ No valid next status for ${licenseData.status} (id ${licenseId})`);
      sleep(0.2);
      return;
    }
    const nextStatus = statusFlow[currentIdx + 1];
    const nextStatusObj = statusFlow[currentIdx + 1];
    const nextStatusString = nextStatusObj.status;  
    const nextRemarksText = nextStatusObj.remarks;  
    const officer = randItem(officerData);
    const payload = {
      licenseId,
      status: nextStatusString,  
      officerName: officer.name,
      role: officer.role,
      remarks: `${nextRemarksText} by ${officer.name} at ${new Date().toISOString()}`,
    };
    if(nextStatusString === 'APPROVED') payload.renewalPeriodDays = 365;

    log(`📋 License ${licenseId}: ${licenseData.status} → ${nextStatusString} (by ${officer.name})`);
    if(__ITER % 250 === 0) log(`DEBUG Payload: ${JSON.stringify(payload)}`);

    // choose account and log occasionally
    const acct = selectAccount();
    if(__ITER % 250 === 0) log(`INFO 🎲 Using random account from pool: ${acct}`);

    // update with bounded retries
    let updateRes = null;
    for(let attempt = 0; attempt < 3; attempt++){
      const startUpdate = nowMs();
      try {
        updateRes = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(payload), JSON_HEADERS, { timeout: '120s' });
      } catch (e) {
        errorRate.add(1);
        log(`❌ POST /license/update-status request error: ${e.message}`);
        // exponential backoff
        sleep(Math.pow(2, attempt) * randInt(1,3));
        continue;
      }
      const updDur = nowMs() - startUpdate;
      statusTrend.add(updDur);
      requestCounter.add(1);
      check(updateRes, { 'Status updated successfully': (r) => [200, 202].includes(r.status) });
      // success path
      if([200,202].includes(updateRes.status)){
        log(`✅ Status update success for ${licenseId}: ${licenseData.status} → ${nextStatusString} (http ${updateRes.status})`);

        // invalidate cache
        cacheInvalidate(licenseId);
        break;
      }
      if (updateRes.status === 200 || updateRes.status === 202) {
          stats.status_ok++; 
      } else {
          stats.status_fail++;
      }
      sleep(1);
      const bodyStr = String(updateRes.body || '').toLowerCase();
      // business logic / bad request -> don't retry
      if(updateRes.status === 400 || bodyStr.includes('already in status') || bodyStr.includes('invalid transition')){
        log(`ℹ️ Business logic prevented update: ${String(updateRes.body).slice(0,200)}`);
        break;
      }

      // transient errors like gas/nonce/429 -> retry
      if(bodyStr.includes('gas') || bodyStr.includes('nonce') || updateRes.status === 429){
        const delay = Math.pow(2, attempt) * randInt(1,4);
        log(`⚠️ Blockchain error for ${licenseId} (attempt ${attempt+1}) - retrying in ${delay}s. status=${updateRes.status}`);
        sleep(delay);
        continue;
      }

      errorRate.add(1);
      log(`❌ Update failed for ${licenseId}: ${updateRes.status} • ${String(updateRes.body).slice(0,200)}`);
      break;
    }

    // If approved, fetch QR & verify
    if(payload.status === 'APPROVED' && updateRes && [200,202].includes(updateRes.status)){
      const startQr = nowMs();
      let qrRes = null;
      try {
        qrRes = http.get(`${BASE_URL}/license/qr/${licenseId}/`, { timeout: '60s' });
      } catch (e) {
        errorRate.add(1);
        log(`❌ GET /license/qr/${licenseId} error: ${e.message}`);
        sleep(0.5);
        return;
      }
      const qrDur = nowMs() - startQr;
      qrTrend.add(qrDur);
      requestCounter.add(1);

      const okQr =  check(qrRes, { 'QR data retrieved': (r) => [200, 202].includes(r.status) });
      if(!okQr){
        stats.qr_fail++;
        log(`❌ QR fetch failed for ${licenseId}: ${qrRes.status}`);
      } else {
        const qrJson = safeJson(qrRes).data || safeJson(qrRes);
        log(`📦 QR data for ${licenseId}: ${JSON.stringify(qrJson).slice(0,200)}`);
        stats.qr_ok++;
        if(qrJson && qrJson.licenseNumber && qrJson.verificationHash){
          const verifyPayload = {
            licenseNumber: qrJson.licenseNumber,
            expectedHash: qrJson.verificationHash,
          };
          const vStart = nowMs();
          let verifyRes = null;
          try {
            verifyRes = http.post(`${BASE_URL}/license/verify/`, JSON.stringify(verifyPayload), JSON_HEADERS, { timeout: '60s' });
          } catch (e) {
            errorRate.add(1);
            log(`❌ POST /license/verify error: ${e.message}`);
            sleep(0.5);
            return;
          }
          const vDur = nowMs() - vStart;
          verifyTrend.add(vDur);
          requestCounter.add(1);

          const okVerify =  check(verifyRes, { 'License verified successfully': (r) => [200, 202].includes(r.status) });
          if(okVerify) {stats.verify_ok++; log(`✅ License ${licenseId} verified successfully`); }
          else {
            errorRate.add(1);
            stats.verify_fail++;
            log(`❌ Verification failed for ${licenseId}: ${verifyRes.status} • ${String(verifyRes.body).slice(0,200)}`);
          }
        } else {
          log(`⚠️ Missing licenseNumber or verificationHash for ${licenseId}`);
        }
      }
    }

    // occasionally refresh RPC stats
    if(__ITER % 3 === 0) simulatedRpcPing();

    sleep(randInt(1,3));
  });
}

// ---------------- TEARDOWN & SUMMARY ----------------
export function teardown(data){
  console.log('\n📊 ======= TEST COMPLETE =======');
  console.log(`✅ License Creation: ${stats.create_ok} successful, ${stats.create_fail} failed`);
  console.log(`✅ Status Updates: ${stats.status_ok} successful, ${stats.status_fail} failed`);
  console.log(`✅ QR Fetches: ${stats.qr_ok} successful, ${stats.qr_fail} failed`);
  console.log(`✅ Verifications: ${stats.verify_ok} successful, ${stats.verify_fail} failed`);

}

// ---------------- SUMMARY REPORT ----------------
export function handleSummary(data) {
  const totalRequests = data.metrics.http_reqs_total?.values?.count || 0;
  const duration = (data.state?.testRunDurationMs || 0) / 1000;
  const tps = duration ? totalRequests / duration : 0;
  const avg = data.metrics.http_req_duration?.values?.avg / 1000 || 0;
  const p95 = data.metrics.http_req_duration?.values['p(95)'] / 1000 || 0;

  console.log(`
  📊 ======= STRESS TEST SUMMARY =======
  🌐 RPC Nodes: ${RPC_URLS.length}
  🔹 Total Requests: ${totalRequests}
  ⚙️  Test Duration: ${duration.toFixed(1)}s
  🚀 TPS: ${tps.toFixed(2)}
  ⏱️  Avg: ${avg.toFixed(2)}s | P95: ${p95.toFixed(2)}s
  `);

  return {
    'stress_test/reports/stress_report.html': htmlReport(data, {
      title: '🌾 Rajasthan Seed Licensing System - Multi-RPC Stress Test',
      theme: 'default',
    }),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
