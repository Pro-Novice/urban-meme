import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend, Counter } from 'k6/metrics';

//HTML report generator 
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
    { duration: '10s', target: 0 }
],
  thresholds: {
    http_req_failed: ['rate<=0.5'],
    http_req_duration: ['p(95)<90000', 'avg<60000'],
  },
  discardResponseBodies: false,
};

// ---------------- CONSTANTS ----------------
const BASE_URL = __ENV.BASE_URL;
const JSON_HEADERS = { headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' } };

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}
function log(msg) {
  console.log(`[VU ${__VU} | ITER ${__ITER}] ${msg}`);
}
function safeJson(res) {
  try {
    return res.json();
  } catch (err) {
    log(`❌ JSON parse error: ${err.message}, body: ${res.body?.substring(0, 150)}`);
    return {};
  }
}

const encryptedAadhaars = new SharedArray('encryptedAadhaars', function () {
    return JSON.parse(open('encrypted_aadhaar.json'));
});


function getEncryptedAadhaar() {
    return encryptedAadhaars[Math.floor(Math.random() * encryptedAadhaars.length)];
}

// ---------------- METRICS ----------------
export let requestCounter = new Counter('http_reqs_total');
export let createTrend = new Trend('License_Create_Duration');
export let statusTrend = new Trend('Status_Update_Duration');
export let verifyTrend = new Trend('Verify_Duration');
export let qrTrend = new Trend('QR_Fetch_Duration');
export let countTrend = new Trend('License_Count_Duration');
export let detailsTrend = new Trend('License_Details_Duration');
export let errorRate = new Counter('errors');

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

// ---------------- GLOBAL STATS ----------------
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

// ---------------- GENERATE APPLICATION ----------------
function generateApplication() {
  const base = randomItem(applicantData);
  return {
    ...base,
    aadhaarNumber: getEncryptedAadhaar(),
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
  console.log('🚀 Starting Rajasthan Seed Licensing Stress Test');
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

// ---------------- MAIN TEST ----------------
export default function () {
  const isCitizen = randomInt(0, 1) === 0;

  if (isCitizen) {
    // Citizen submitting license application
    group('Citizen: License Creation', () => {
      const payload = generateApplication();
      const start = new Date().getTime();
      const res = http.post(`${BASE_URL}/license/create/`, JSON.stringify(payload), JSON_HEADERS);
      const duration = res.timings.duration;
      createTrend.add(new Date().getTime() - start);
      requestCounter.add(1);
      log(`🟢 POST /license/create → ${res.status} (${duration.toFixed(0)} ms)`);
      
      check(res, { 'Application submitted successfully': (r) => [200, 201, 202].includes(r.status) });
      if ([200, 201, 202].includes(res.status)) stats.create_ok++;
      else {
        stats.create_fail++;
        log(`❌ License Creation Failed:
          • Status: ${res.status}
          • Response Body: ${res.body ? res.body.substring(0, 400) : '[Empty response]'}`);
      }

      sleep(randomInt(2, 3));
    });
  } else {
    // Officer performing workflow updates
    group('Officer: License Workflow', () => {
      const countRes = http.get(`${BASE_URL}/license/count/`);
      const start = new Date().getTime();
      countTrend.add(new Date().getTime() - start);
      requestCounter.add(1);
      if (countRes.status !== 200) {
        sleep(1);
        return;
      }
      const countJson = safeJson(countRes);
      check(countRes, { 'License count retrieved': (r) => r.status === 200 });
      if (countRes.status !== 200 || !countJson.data) return;

      const total = countJson.data || 0;
      if (total === 0) return;

      const licenseId = randomInt(1, total);
      const detailsRes = http.get(`${BASE_URL}/license/info/${licenseId}/`);
      detailsTrend.add(new Date().getTime() - start);
      requestCounter.add(1);
      if (detailsRes.status !== 200) {
        sleep(0.5);
        return;
      }
      const license = safeJson(detailsRes).data;
      check(detailsRes, { 'License details retrieved': (r) => r.status === 200 });
      if (!license || ['APPROVED', 'REJECTED', 'REVOKED'].includes(license.status)) return;

      const idx = statusFlow.findIndex((s) => s.status === license.status) + 1;
      const next = statusFlow[idx];
      if (!next) return;

      const officer = randomItem(officerData);
      const payload = {
        licenseId,
        status: next.status,
        officerName: officer.name,
        role: officer.role,
        remarks: next.remarks,
        ...(next.status === 'APPROVED' && { renewalPeriodDays: next.renewalPeriodDays }),
      };
      log(`📋 License ${licenseId} current status: ${license.status}, attempting to move to: ${next.status}`);
      log(`🧾 Payload: ${JSON.stringify(payload)}`);

      let updateRes;
      for (let i = 0; i < 3; i++) {
        const start = new Date().getTime();
        updateRes = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(payload), JSON_HEADERS);
        statusTrend.add(new Date().getTime() - start);
        requestCounter.add(1);
        if ([200, 202].includes(updateRes.status)) {
          log(`✅ POST /update-status success for license ${licenseId}`);
          stats.status_ok++;
          check(updateRes, { 'Status updated successfully': (r) => [200, 202].includes(r.status) });
          break;
        } else if (updateRes.body?.includes('gas limit')) {
          const delay = 2 ** i * randomInt(3, 8);
          log(`⚠️ Gas limit exceeded for license ${licenseId}, retrying in ${delay}s...`);
          sleep(delay);
        } else {
          log(`❌ Update failed for license ${licenseId}: ${updateRes.status}`);
          stats.status_fail++;
          break;
        }
      }
      sleep(1);
      if (payload.status === 'APPROVED' && [200, 202].includes(updateRes?.status)) {
      const qrRes = http.get(`${BASE_URL}/license/qr/${licenseId}/`);
      qrTrend.add(new Date().getTime() - start);
      requestCounter.add(1);
      check(qrRes, { 'QR data retrieved': (r) => [200, 202].includes(r.status) });

      if ([200, 202].includes(qrRes.status)) {
        const qr = safeJson(qrRes)?.data || {};
        log(`📦 QR data for ${licenseId}: ${JSON.stringify(qr)}`);

        if (qr?.licenseNumber && qr?.verificationHash) {
          const verifyPayload = {
            licenseNumber: qr.licenseNumber,
            expectedHash: qr.verificationHash,
          };
          const start = new Date().getTime();
          const verifyRes = http.post(`${BASE_URL}/license/verify/`, JSON.stringify(verifyPayload), JSON_HEADERS);
          verifyTrend.add(new Date().getTime() - start);
          requestCounter.add(1);
          log(`🔵 POST /license/verify → ${verifyRes.status}`);
          check(verifyRes, { 'License verified successfully': (r) => [200, 202].includes(r.status) });
        } else {
          log(`⚠️ Missing licenseNumber or verificationHash for ${licenseId}`);
        }
      }
    }
    sleep(randomInt(0.5, 2));
  });
  }
}

// ---------------- HTML REPORT GENERATION ----------------
export function handleSummary(data) {
  const totalRequestsCount = data.metrics.http_reqs_total?.values.count || 0;
  const testDuration = (data.state?.testRunDurationMs || 0) / 1000; 
  const tps = testDuration > 0 ? totalRequestsCount / testDuration : 0;
  const avgResTime = data.metrics.http_req_duration?.values.avg
    ? data.metrics.http_req_duration.values.avg / 1000
    : 0;
  const p95ResTime = data.metrics.http_req_duration?.values['p(95)']
    ? data.metrics.http_req_duration.values['p(95)'] / 1000
    : 0;

  console.log(`
    📊 ======= STRESS TEST SUMMARY =======
    🔹 Total Requests: ${totalRequestsCount}
    ⚙️  Test Duration: ${testDuration.toFixed(2)}s
    🚀 Throughput (TPS): ${tps.toFixed(2)} req/s
    ⏱️  Avg Response Time: ${avgResTime.toFixed(2)}s
    🔥 P(95) Response Time: ${p95ResTime.toFixed(2)}s
  `);
  return {
    'stress_report.html': htmlReport(data, {
      title: '🌾 Rajasthan Seed Licensing System - Stress Test Report',
      theme: 'default', 
    }),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
