import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Metrics
const errorRate = new Rate('errors');
const txDuration = new Trend('blockchain_tx_duration', true);

export const options = {
  stages: [
    { duration: '20s', target: 2 },
    { duration: '40s', target: 2 },
    { duration: '20s', target: 5 },
    { duration: '1m', target: 5 },
    { duration: '20s', target: 10 },
    { duration: '40s', target: 10 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<20000'],
    http_req_failed: ['rate<0.05'],
    blockchain_tx_duration: ['p(95)<35000'],
  }
};

const BASE_URL = __ENV.BASE_URL || 'http://10.70.233.251:8000/api/blockchain';
const requestOptions = {
  headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
  timeout: '60s'
};

const basePayload = {
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

function generateUniquePayload() {
  const ts = Date.now();
  const rnd = Math.floor(Math.random() * 10000);
  const names = ['Ravi Kumar', 'Amit Sharma', 'Priya Singh', 'Vikash Gupta', 'Sunita Devi'];
  const firms = ['Ravi Agro Traders', 'Green Farm Solutions', 'Krishi Connect', 'Agro Plus', 'Farm Tech'];
  const crops = ['Wheat', 'Rice', 'Maize', 'Barley', 'Mustard'];
  const varieties = ['HD2967', 'PB1121', 'DHM117', 'RD2715', 'Pusa Bold'];

  return {
    ...basePayload,
    applicantName: `${names[Math.floor(Math.random() * names.length)]}_${ts}`,
    firmName: `${firms[Math.floor(Math.random() * firms.length)]}_${rnd}`,
    cropName: crops[Math.floor(Math.random() * crops.length)],
    cropVariety: varieties[Math.floor(Math.random() * varieties.length)],
    aadhaarNumber: (Math.floor(Math.random() * 900000000000) + 100000000000).toString()
  };
}

function updateStatus(licenseId, status, role = 'AGRICULTURE_OFFICER') {
  const payload = {
    licenseId,
    status,
    officerName: 'Shrawan',
    role,
    remarks: `Status changed to ${status}`
  };
  if (status === 'APPROVED' || status === 'RENEWED') {
    payload.renewalPeriodDays = 30;
  }
  const res = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(payload), {
    ...requestOptions,
    tags: { endpoint: 'license-update-status' }
  });
  const ok = check(res, {
    [`Status ${status} OK`]: (r) => r.status === 200 || r.status === 201
  });
  if (!ok) {
    errorRate.add(1);
    console.error(`Status update to ${status} failed: ${res.status} - ${res.body}`);
  }
  sleep(1);
}

export default function () {
  const vu = __VU;
  const iter = __ITER;

  // Step 1: Create license
  const payload = generateUniquePayload();
  const start = Date.now();
  const createRes = http.post(`${BASE_URL}/license/create/`, JSON.stringify(payload), {
    ...requestOptions,
    tags: { endpoint: 'license-create' }
  });
  txDuration.add(Date.now() - start);

  if (!(createRes.status === 200 || createRes.status === 201)) {
    errorRate.add(1);
    console.error(`[VU:${vu}][Iter:${iter}] License creation failed: ${createRes.status} ${createRes.body}`);
    return;
  }

  let licenseId;
  try {
    const data = JSON.parse(createRes.body);
	  console.log(data);
    licenseId = data?.data?.license_id || data?.licenseId || data?.id;
  } catch (e) {
    console.error(`Error parsing create response: ${e}`);
    return;
  }

  if (!licenseId) {
    console.error(`No licenseId returned — stopping VU`);
    return;
  }

  // Step 2: Get current status
  let currentStatus = null;
  const infoRes = http.get(`${BASE_URL}/license/${licenseId}/info/`, {
    ...requestOptions,
    tags: { endpoint: 'license-info' }
  });
  if (infoRes.status === 200) {
    try {
      const info = JSON.parse(infoRes.body);
      currentStatus = info?.data?.status;
    } catch {}
  }

  if (!currentStatus) {
    console.error(`Could not determine current status for license ${licenseId}`);
    return;
  }

  // Step 3: Valid sequence and remaining statuses
  const validSequence = [
	  'SUBMITTED',
    'UNDER_REVIEW',
    'DOCUMENTS_VERIFIED',
    'INSPECTION_SCHEDULED',
    'INSPECTION_COMPLETED',
    'APPROVED'
  ];

  const startIndex = validSequence.indexOf(currentStatus);
  if (startIndex === -1) {
    console.error(`Unknown current status ${currentStatus} for license ${licenseId}`);
    return;
  }

  const remainingStatuses = validSequence.slice(startIndex + 1);
  remainingStatuses.forEach((status) => updateStatus(licenseId, status));

  // Step 4: QR code (only after approved)
  let qrLicenseNumber = null;
  let qrExpectedHash = null;

  if (remainingStatuses.includes('APPROVED') || currentStatus === 'APPROVED') {
    const qrRes = http.get(`${BASE_URL}/license/${licenseId}/qr/`, {
      ...requestOptions,
      tags: { endpoint: 'license-qr' }
    });

    if (qrRes.status === 200) {
      try {
        const qrData = JSON.parse(qrRes.body);
        qrLicenseNumber = qrData?.data?.licenseNumber;
        qrExpectedHash = qrData?.data?.verificationHash;
      } catch (e) {
        console.error(`Error parsing QR response for license ${licenseId}: ${e}`);
      }
    }
  }

  // Step 5: History
  http.get(`${BASE_URL}/license/${licenseId}/history/`, {
    ...requestOptions,
    tags: { endpoint: 'license-history' }
  });

  // Step 6: Verify (only if we got QR data)
  if (qrLicenseNumber && qrExpectedHash) {
    const verifyPayload = {
      licenseNumber: qrLicenseNumber,
      expectedHash: qrExpectedHash
    };
    http.post(`${BASE_URL}/license/verify/`, JSON.stringify(verifyPayload), {
      ...requestOptions,
      tags: { endpoint: 'license-verify' }
    });
  }

  // Step 7: Update details
  const updatePayload = {
    license_id: licenseId,
    firm_name: 'Updated Firm Name',
    firm_type: 'Updated Firm Type',
    firm_address: 'Updated Firm Address',
    sale_point_address: 'Updated Sale Point Address',
    crop_variety: 'Updated Crop Variety',
    role: 'JOINT_DIRECTOR'
  };
  http.post(`${BASE_URL}/license/update/`, JSON.stringify(updatePayload), {
    ...requestOptions,
    tags: { endpoint: 'license-update' }
  });
}

export function setup() {
  console.log(`Starting blockchain license lifecycle test on: ${BASE_URL}`);
}

export function teardown() {
  console.log('Blockchain license lifecycle test completed');
}

