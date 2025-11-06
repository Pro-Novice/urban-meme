import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend, Counter } from 'k6/metrics';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.1.0/index.js';

// ---------------- CONFIG ----------------
export const options = {
  stages: [
    { duration: '10s', target: 100 },
    { duration: '10s', target: 300 },
    { duration: '10s', target: 500 },
    { duration: '10s', target: 500 },
    { duration: '10s', target: 500 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<=0.5'],
    http_req_duration: ['p(95)<90000', 'avg<60000'],
  },
  discardResponseBodies: false,
};

// ---------------- ENVIRONMENT ----------------
const BASE_URL = __ENV.BASE_URL;
const RPC_URLS = (__ENV.RPC_URLS || 'http://host.docker.internal:8545').split(',');
const JSON_HEADERS = { headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' } };

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}
function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
function log(msg) {
  console.log(`[VU ${__VU} | ITER ${__ITER}] ${msg}`);
}
function safeJson(res) {
  try {
    return res.json();
  } catch (err) {
    log(`❌ JSON parse error: ${err.message}`);
    return {};
  }
}

// ---------------- SHARED DATA ----------------
const encryptedAadhaars = new SharedArray('encryptedAadhaars', () => {
  try {
    return JSON.parse(open('encrypted_aadhaar.json'));
  } catch (e) {
    console.error(`⚠️ Failed to load encrypted_aadhaar.json: ${e}`);
    return ['default_encrypted_aadhaar'];
  }
});

// ---------------- METRICS ----------------
export let requestCounter = new Counter('http_reqs_total');
export let createTrend = new Trend('License_Create_Duration');
export let rpcPingTrend = new Trend('RPC_Ping_Duration');

// ---------------- RPC LOAD-BALANCING LOGIC ----------------
function selectRpcUrl() {
  return randomItem(RPC_URLS);
}

function simulateRpcPing() {
  const url = selectRpcUrl();
  const start = Date.now();
  try {
    const res = http.post(`${BASE_URL}/blockchain/rpc-ping/`, JSON.stringify({ rpcUrl: url }), JSON_HEADERS);
    rpcPingTrend.add(Date.now() - start);
    if (res.status === 200) {
      log(`🌐 RPC Ping OK → ${url}`);
    } else {
      log(`⚠️ RPC Ping failed → ${url}, status: ${res.status}`);
    }
  } catch (e) {
    log(`❌ RPC Ping error → ${url}: ${e}`);
  }
}

// ---------------- TEST DATA ----------------
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
]);

function generateApplication() {
  const base = randomItem(applicantData);
  return {
    ...base,
    aadhaarNumber: randomItem(encryptedAadhaars),
    registeringAuthority: 'Department of Agriculture',
    registeringOfficeName: `District Agri Office, ${randomItem(['Jaipur', 'Udaipur', 'Jodhpur', 'Kota'])}`,
    applicantPermanentAddress: `H.No ${randomInt(1, 100)}, ${randomItem(['Green', 'Royal', 'Sunrise'])} Colony`,
    firmAddress: `Plot No ${randomInt(1, 50)}, ${randomItem(['Mandi Road', 'Industrial Area', 'Agro Park'])}`,
    salePointAddress: `Shop No ${randomInt(1, 20)}, ${randomItem(['Krishi Market', 'Farmer Plaza', 'Agri Complex'])}`,
    saleStorageAddress: `Warehouse ${randomInt(1, 10)}, ${randomItem(['Outer Ring Road', 'Storage Zone', 'Logistics Park'])}`,
  };
}

// ---------------- SETUP ----------------
export function setup() {
  console.log('🚀 Starting Rajasthan Seed Licensing K6 Stress Test');
  try {
    const res = http.get(`${BASE_URL}/owner/`);
    if (res.status === 200) console.log('✅ Backend reachable');
    else console.error(`❌ Backend not reachable: ${res.status}`);
  } catch (e) {
    console.error(`❌ Setup error: ${e}`);
  }

  console.log(`🌐 RPC nodes registered: ${RPC_URLS.join(', ')}`);
}

// ---------------- MAIN TEST ----------------
export default function () {
  const isCitizen = randomInt(0, 1) === 0;

  if (isCitizen) {
    group('Citizen: License Creation', () => {
      const payload = generateApplication();
      const start = Date.now();
      const res = http.post(`${BASE_URL}/license/create/`, JSON.stringify(payload), JSON_HEADERS);
      const duration = Date.now() - start;
      createTrend.add(duration);
      requestCounter.add(1);
      log(`🟢 POST /license/create → ${res.status} (${duration} ms)`);

      check(res, { 'License creation successful': (r) => [200, 201, 202].includes(r.status) });

      // During bursts — ping multiple RPCs to simulate backend load balancing
      if (__ITER % 5 === 0) {
        for (let i = 0; i < RPC_URLS.length; i++) {
          simulateRpcPing();
        }
      }

      sleep(randomInt(1, 3));
    });
  } else {
    group('System: RPC Load Balancing Simulation', () => {
      // Each officer iteration randomly stresses RPC nodes
      const parallelPings = randomInt(2, 4);
      for (let i = 0; i < parallelPings; i++) {
        simulateRpcPing();
      }
      sleep(randomInt(0.5, 1.5));
    });
  }
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
    'stress_report.html': htmlReport(data, {
      title: '🌾 Rajasthan Seed Licensing System - Multi-RPC Stress Test',
      theme: 'default',
    }),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
