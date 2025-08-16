import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const txDuration = new Trend('blockchain_tx_duration', true);
const statusUpdateDuration = new Trend('status_update_duration', true);

// Combined Load + Stress test configuration for blockchain backend
export const options = {
  stages: [
    // --- Load Testing Phase ---
    { duration: '30s', target: 2 },   // Initial slow ramp-up
    { duration: '1m', target: 2 },    // Low steady load
    { duration: '30s', target: 5 },   // Gradual increase
    { duration: '2m', target: 5 },    // Medium steady load

    // --- Stress Testing Phase ---
    { duration: '30s', target: 10 },  // Push toward upper limit
    { duration: '1m', target: 10 },   // Hold high load to find bottlenecks
    { duration: '30s', target: 15 },  // Spike to extreme load (stress point)
    { duration: '45s', target: 15 },  // Sustain extreme load briefly

    // --- Recovery & Ramp-down ---
    { duration: '30s', target: 5 },   // Drop to medium load
    { duration: '1m', target: 2 },    // Drop to low load
    { duration: '30s', target: 0 },   // Ramp down to zero
  ],
  thresholds: {
    http_req_duration: ['p(95)<25000'],        // 25s max for blockchain operations
    http_req_failed: ['rate<0.05'],            // <5% failure rate
    'checks{endpoint:license-create}': ['rate>0.90'], // License creation >90% success
    'checks{endpoint:license-count}': ['rate>0.95'],  // Count endpoint >95% success
    'checks{endpoint:license-info}': ['rate>0.95'],   // Info endpoint >95% success
    'checks{endpoint:status-update}': ['rate>0.90'],  // Status updates >90% success
    'checks{endpoint:qr-data}': ['rate>0.85'],        // QR data >85% success (only for approved)
    blockchain_tx_duration: ['p(95)<35000'],          // 95% of transactions <35s
    status_update_duration: ['p(95)<20000'],          // Status updates <20s
  }
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/api/blockchain';

const headers = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
  'Connection': 'keep-alive',
};

const requestOptions = {
  headers: headers,
  timeout: '60s',
};

// Status transition order
const STATUS_FLOW = [
  'SUBMITTED',
  'UNDER_REVIEW',
  'DOCUMENTS_VERIFIED',
  'INSPECTION_SCHEDULED',
  'INSPECTION_COMPLETED',
  'APPROVED'
];

const licensePayload = {
  licenseCategory: 'SEED',
  licenseLevel: 'DISTRICT',
  registeringAuthority: 'Department of Agriculture',
  registeringOfficeName: 'District Agri Office, Jaipur',
  applicantName: 'Ravi Kumar',
  aadhaarNumber: '123456789012',
  applicantPermanentAddress: 'H.No 45, Green Colony, Jaipur',
  firmName: 'Ravi Agro Traders',
  firmType: 'Partnership',
  firmAddress: 'Plot No 22, Mandi Road, Jaipur',
  salePointAddress: 'Shop No 5, Krishi Market, Jaipur',
  saleStorageAddress: 'Warehouse No 3, Outer Ring Road, Jaipur',
  cropName: 'Wheat',
  cropVariety: 'HD2967',
  isSeedSelfProduced: false,
  productionCompany: 'Agro Seeds Pvt Ltd',
};

const officers = [
  { name: 'Shrawan Singh', role: 'AGRICULTURE_OFFICER' },
  { name: 'Priya Sharma', role: 'JOINT_DIRECTOR' },
  { name: 'Rajesh Gupta', role: 'FIELD_INSPECTOR' },
  { name: 'Sunita Singh', role: 'AGRICULTURE_OFFICER' },
];

function generateUniquePayload() {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);

  const names = ['Ravi Kumar', 'Amit Sharma', 'Priya Singh', 'Vikash Gupta', 'Sunita Devi'];
  const firms = ['Ravi Agro Traders', 'Green Farm Solutions', 'Krishi Connect', 'Agro Plus', 'Farm Tech'];
  const crops = ['Wheat', 'Rice', 'Maize', 'Barley', 'Mustard'];
  const varieties = ['HD2967', 'PB1121', 'DHM117', 'RD2715', 'Pusa Bold'];
  const companies = ['Agro Seeds Pvt Ltd', 'Krishi Tech', 'Green Valley Seeds', 'Farm Pro', 'Seed Masters'];

  const payload = { ...licensePayload };
  payload.applicantName = `${names[Math.floor(Math.random() * names.length)]}_${timestamp}`;
  payload.firmName = `${firms[Math.floor(Math.random() * firms.length)]}_${random}`;
  payload.cropName = crops[Math.floor(Math.random() * crops.length)];
  payload.cropVariety = varieties[Math.floor(Math.random() * varieties.length)];
  payload.productionCompany = companies[Math.floor(Math.random() * companies.length)];
  payload.aadhaarNumber = (Math.floor(Math.random() * 900000000000) + 100000000000).toString();

  return payload;
}

function createStatusUpdatePayload(licenseId, statusIndex) {
  const officer = officers[Math.floor(Math.random() * officers.length)];
  const status = STATUS_FLOW[statusIndex];

  const payload = {
    licenseId: licenseId,
    status: status,
    officerName: officer.name,
    role: officer.role,
    remarks: `License is ${status} by ${officer.name}`
  };

  // Add renewal period for APPROVED status
  if (status === 'APPROVED' || status == 'RENEWED') {
    payload.renewalPeriodDays = Math.floor(Math.random() * 365) + 30; // 30-395 days
  }

  return payload;
}

// Shared state for tracking created licenses and their status
let createdLicenses = [];

export default function () {
  const vuId = __VU;
  const iterationId = __ITER;

  // --- POST /license/create/ ---
  const payload = generateUniquePayload();
  const startTime = Date.now();

  const licenseCreateResponse = http.post(
    `${BASE_URL}/license/create/`,
    JSON.stringify(payload),
    {
      ...requestOptions,
      tags: { endpoint: 'license-create' },
    }
  );

  const createDuration = Date.now() - startTime;
  txDuration.add(createDuration);

  let licenseId = null;
  let responseBody = null;

  // Extract license ID first
  if (licenseCreateResponse.status === 200 || licenseCreateResponse.status === 201) {
    try {
      responseBody = JSON.parse(licenseCreateResponse.body);
      if (responseBody && responseBody.data) {
        // Try different possible response structures
        licenseId = responseBody.data.licenseId || responseBody.data.license_id || responseBody.data.id;
        console.log(`[VU:${vuId}][Iter:${iterationId}] Extracted License ID: ${licenseId} from response: ${JSON.stringify(responseBody.data).substring(0, 200)}`);
      }
    } catch (e) {
      console.error(`[VU:${vuId}][Iter:${iterationId}] Failed to parse license creation response: ${e}`);
    }
  }

  const licenseOK = check(licenseCreateResponse, {
    'License POST: status 200/201': (r) => r.status === 200 || r.status === 201,
    'License POST: not timeout': (r) => r.status !== 0,
    'License POST: response time < 35s': (r) => r.timings.duration < 35000,
    'License POST: valid JSON response': (r) => {
      if (r.status === 0) return false;
      return responseBody !== null;
    },
  }, { endpoint: 'license-create' });

  if (!licenseOK || !licenseId) {
    errorRate.add(1);
    console.error(`[VU:${vuId}][Iter:${iterationId}] License CREATE failed: Status=${licenseCreateResponse.status}, Duration=${createDuration}ms, Body=${licenseCreateResponse.body?.substring(0, 300)}`);
    sleep(Math.random() * 3 + 2);
    return;
  } else {
    console.log(`[VU:${vuId}][Iter:${iterationId}] License CREATE success: Status=${licenseCreateResponse.status}, Duration=${createDuration}ms, LicenseID=${licenseId}`);
    createdLicenses.push({ id: licenseId, currentStatusIndex: 0 }); // Start with SUBMITTED
  }

  sleep(1);

  // --- GET /license/count/ ---
  const countResponse = http.get(`${BASE_URL}/license/count/`, {
    ...requestOptions,
    tags: { endpoint: 'license-count' },
  });

  const countOK = check(countResponse, {
    'License COUNT: status is 200': (r) => r.status === 200,
    'License COUNT: response time < 10s': (r) => r.timings.duration < 10000,
    'License COUNT: valid JSON': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body && body.success !== false;
      } catch {
        return false;
      }
    },
  }, { endpoint: 'license-count' });

  if (!countOK) {
    errorRate.add(1);
    console.error(`[VU:${vuId}][Iter:${iterationId}] License COUNT failed: Status=${countResponse.status}, Body=${countResponse.body?.substring(0, 200)}`);
  }

  sleep(1);

  // Use the newly created license ID - don't use random IDs that might not exist
  const targetLicenseId = licenseId;

  // --- GET /license/{id}/info/ ---
  const infoResponse = http.get(`${BASE_URL}/license/${targetLicenseId}/info/`, {
    ...requestOptions,
    tags: { endpoint: 'license-info' },
  });

  const infoOK = check(infoResponse, {
    'License INFO: status is 200': (r) => r.status === 200,
    'License INFO: response time < 15s': (r) => r.timings.duration < 15000,
    'License INFO: valid JSON': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body && body.success !== false;
      } catch {
        return false;
      }
    },
  }, { endpoint: 'license-info' });

  if (!infoOK) {
    errorRate.add(1);
    console.error(`[VU:${vuId}][Iter:${iterationId}] License INFO failed: Status=${infoResponse.status}, LicenseID=${targetLicenseId}, Body=${infoResponse.body?.substring(0, 200)}`);
  }

  sleep(1);

  // --- POST /license/update-status/ ---
  // Use the newly created license for status update
  const nextStatusIndex = 1; // Move from SUBMITTED to UNDER_REVIEW
  const statusPayload = createStatusUpdatePayload(licenseId, nextStatusIndex);

  const statusStartTime = Date.now();
  const statusUpdateResponse = http.post(
    `${BASE_URL}/license/update-status/`,
    JSON.stringify(statusPayload),
    {
      ...requestOptions,
      tags: { endpoint: 'status-update' },
    }
  );

  const statusDuration = Date.now() - statusStartTime;
  statusUpdateDuration.add(statusDuration);

  const statusOK = check(statusUpdateResponse, {
    'Status UPDATE: status 200/201': (r) => r.status === 200 || r.status === 201,
    'Status UPDATE: not timeout': (r) => r.status !== 0,
    'Status UPDATE: response time < 20s': (r) => r.timings.duration < 20000,
    'Status UPDATE: valid response': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body && body.success !== false;
      } catch {
        return false;
      }
    },
  }, { endpoint: 'status-update' });

  if (statusOK) {
    console.log(`[VU:${vuId}][Iter:${iterationId}] Status UPDATE success: LicenseID=${licenseId}, Status=${STATUS_FLOW[nextStatusIndex]}, Duration=${statusDuration}ms`);
    // Update the license status in our tracking
    const licenseEntry = createdLicenses.find(l => l.id === licenseId);
    if (licenseEntry) {
      licenseEntry.currentStatusIndex = nextStatusIndex;
    }
  } else {
    errorRate.add(1);
    console.error(`[VU:${vuId}][Iter:${iterationId}] Status UPDATE failed: Status=${statusUpdateResponse.status}, LicenseID=${licenseId}, Duration=${statusDuration}ms, Body=${statusUpdateResponse.body?.substring(0, 200)}`);
  }

  // Randomly test some additional endpoints
  if (Math.random() < 0.3) { // 30% chance
    // --- POST /license/verify/ ---
    const verifyPayload = {
      licenseNumber: `RJSDST${Math.floor(Math.random() * 100) + 1}`,
      expectedHash: '212d02520d33be03153a2c34cb4d50b63f570e6d6881589ebbec2ec6b3da51b0'
    };

    const verifyResponse = http.post(
      `${BASE_URL}/license/verify/`,
      JSON.stringify(verifyPayload),
      {
        ...requestOptions,
        tags: { endpoint: 'license-verify' },
      }
    );

    check(verifyResponse, {
      'License VERIFY: has response': (r) => r.status !== 0,
      'License VERIFY: response time < 20s': (r) => r.timings.duration < 20000,
    }, { endpoint: 'license-verify' });
  }

  if (Math.random() < 0.2) { // 20% chance
    // --- GET /contract/all/address/ ---
    const contractResponse = http.get(`${BASE_URL}/contract/all/address/`, {
      ...requestOptions,
      tags: { endpoint: 'contract-address' },
    });

    check(contractResponse, {
      'Contract ADDRESS: status is 200': (r) => r.status === 200,
      'Contract ADDRESS: response time < 10s': (r) => r.timings.duration < 10000,
    }, { endpoint: 'contract-address' });
  }

  // Blockchain cooldown
  sleep(Math.random() * 5 + 3); // 3–8s
}

export function setup() {
  console.log(`Starting comprehensive blockchain load+stress test against: ${BASE_URL}`);

  // Test basic connectivity with license count instead of owner
  const response = http.get(`${BASE_URL}/license/count/`, { timeout: '10s' });
  if (response.status !== 200) {
    throw new Error(`Server not accessible: ${response.status}`);
  }

  console.log('Server connectivity verified. Test starting...');
  return {};
}

export function teardown(data) {
  console.log('Comprehensive blockchain load+stress test completed');
  console.log(`Total licenses tracked: ${createdLicenses.length}`);
}