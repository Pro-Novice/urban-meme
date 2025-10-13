import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';

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
const BASE_URL = 'http://127.0.0.1:8000/api/blockchain';
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

// ---------------- TEST DATA ----------------
const applicantData = new SharedArray('applicants', () => [
  {
    licenseCategory: 'SEED',
    licenseLevel: 'DISTRICT',
    applicantName: 'Ravi Kumar',
    aadhaarNumber:
      'IRk4zRfT9iJvf5CRYUQOZwor9ro553k8mWwlfqwLPheTWoz0oLEPlr/+4vPOPOa0nOROMII9ZhLV9r2DR1AnPqsVXUj2g1JiAZWvIE61Zu/qU/RU/B+yxUnbmztYC8kmK0eunlvFyNtmBidbgbatQWnn4JufcuewGFwCIUblTCQ9PpPouh8KK9602n4rPi36MGcGQFVdm8uoxig9/RRLh34UFb8yBamhuY5I/5UMDQUgli5Vu9Fc8AXuu+3sZ3odR8DIeMykmtTyrysTYAu7I8jHHThGcHNiysrESgaPEc5azFdFHdULoLiWA4RRMrgKDFWJV1MeTbI1UZsHtCc/PA==',
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
  const res = http.get(`${BASE_URL}/owner/`);
  console.log(`API connectivity check: ${res.status}`);
  if (res.status !== 200) {
    console.error('❌ Backend not reachable — check Django + blockchain nodes.');
  } else {
    console.log('✅ Backend reachable. Proceeding...');
  }
}

// ---------------- MAIN TEST ----------------
export default function () {
  const isCitizen = randomInt(0, 1) === 0;

  if (isCitizen) {
    // Citizen submitting license application
    group('Citizen: License Creation', () => {
      const payload = generateApplication();
      const res = http.post(`${BASE_URL}/license/create/`, JSON.stringify(payload), JSON_HEADERS);
      const duration = res.timings.duration;
      log(`🟢 POST /license/create → ${res.status} (${duration.toFixed(0)} ms)`);

      check(res, { 'Application submitted successfully': (r) => [200, 201, 202].includes(r.status) });
      if ([200, 201, 202].includes(res.status)) stats.create_ok++;
      else stats.create_fail++;
      sleep(randomInt(1, 3));
    });
  } else {
    // Officer performing workflow updates
    group('Officer: License Workflow', () => {
      const countRes = http.get(`${BASE_URL}/license/count/`);
      if (countRes.status !== 200) {
        sleep(2);
        return;
      }
      const countJson = safeJson(countRes);
      check(countRes, { 'License count retrieved': (r) => r.status === 200 });
      if (countRes.status !== 200 || !countJson.data) return;

      const total = countJson.data || 0;
      if (total === 0) return;

      const licenseId = randomInt(1, total);
      const detailsRes = http.get(`${BASE_URL}/license/info/${licenseId}/`);
      if (detailsRes.status !== 200) {
        sleep(2);
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
        updateRes = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(payload), JSON_HEADERS);
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
      sleep(3);
      if (payload.status === 'APPROVED' && [200, 202].includes(updateRes?.status)) {
      const qrRes = http.get(`${BASE_URL}/license/qr/${licenseId}/`);
      check(qrRes, { 'QR data retrieved': (r) => [200, 202].includes(r.status) });

      if ([200, 202].includes(qrRes.status)) {
        const qr = safeJson(qrRes)?.data || {};
        log(`📦 QR data for ${licenseId}: ${JSON.stringify(qr)}`);

        if (qr?.licenseNumber && qr?.verificationHash) {
          const verifyPayload = {
            licenseNumber: qr.licenseNumber,
            expectedHash: qr.verificationHash,
          };
          const verifyRes = http.post(`${BASE_URL}/license/verify/`, JSON.stringify(verifyPayload), JSON_HEADERS);
          log(`🔵 POST /license/verify → ${verifyRes.status}`);
          check(verifyRes, { 'License verified successfully': (r) => [200, 202].includes(r.status) });
        } else {
          log(`⚠️ Missing licenseNumber or verificationHash for ${licenseId}`);
        }
      }
    }
    sleep(randomInt(1, 3));
  });
  }
}
