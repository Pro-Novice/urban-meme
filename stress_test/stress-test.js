import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';

// Configuration ---
export const options = {
  stages: [
    { duration: '30s', target: 50 },     // warmup
    { duration: '30s', target: 200 },    // ramp higher
    { duration: '30s', target: 500 },    // push load
    { duration: '30s', target: 500 },   // stress
    { duration: '30s', target: 500 },   // peak stress
    { duration: '3s', target: 0 },      // ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.2'],      // allow up to 20% failures
    http_req_duration: ['p(95)<8000'],  // 95% requests < 8s
  },
  discardResponseBodies: false,
};
// Base configuration ---
const BASE_URL = 'http://127.0.0.1:8000/api/blockchain';
const JSON_HEADERS = { headers: { 'Content-Type': 'application/json' } };

function randomIntBetween(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}
function log(message) {
  console.log(`[VU ${__VU} | ITER ${__ITER}] ${message}`);
}

const applicantData = new SharedArray('applicants', () => [
  {
    licenseCategory: 'SEED',
    licenseLevel: 'DISTRICT',
    applicantName: 'Ravi Kumar',
    aadhaarNumber: '123456789012',
    firmName: 'Ravi Agro Traders',
    firmType: 'Partnership',
    cropName: 'Wheat',
    cropVariety: 'HD2967',
    isSeedSelfProduced: false,
    productionCompany: 'Sharma Seeds Pvt Ltd'
  },
  {
    licenseCategory: 'SEED',
    licenseLevel: 'STATE',
    applicantName: 'Priya Sharma',
    aadhaarNumber: '987654321098',
    firmName: 'Sharma Seeds',
    firmType: 'Proprietorship',
    cropName: 'Rice',
    cropVariety: 'PR126',
    isSeedSelfProduced: true,
    productionCompany: 'Sharma Seeds Pvt Ltd'
  },
  {
    licenseCategory: 'SEED',
    licenseLevel: 'DISTRICT',
    applicantName: 'Vijay Singh',
    aadhaarNumber: '564738291023',
    firmName: 'Vijay Agro',
    firmType: 'LLP',
    cropName: 'Maize',
    cropVariety: 'PMH1',
    isSeedSelfProduced: false,
    productionCompany: 'Sharma Seeds Pvt Ltd'
  }
]);

const officerData = [
  { name: 'Shrawan', role: 'AGRICULTURE_OFFICER' },
  { name: 'Rajesh', role: 'JOINT_DIRECTOR' },
  { name: 'Meena', role: 'DEPUTY_DIRECTOR' },
  { name: 'Arun', role: 'DIRECTOR' }
];

const statusFlow = [
  { status: 'SUBMITTED', remarks: 'Application submitted' },
  { status: 'UNDER_REVIEW', remarks: 'Application under review' },
  { status: 'DOCUMENTS_VERIFIED', remarks: 'Documents verified' },
  { status: 'INSPECTION_SCHEDULED', remarks: 'Inspection scheduled' },
  { status: 'INSPECTION_COMPLETED', remarks: 'Inspection completed' },
  { status: 'APPROVED', remarks: 'License approved', renewalPeriodDays: 365 }
];

function generateApplication() {
  const base = randomItem(applicantData);
  return {
    ...base,
    registeringAuthority: 'Department of Agriculture',
    registeringOfficeName: `District Agri Office, ${randomItem(['Jaipur', 'Udaipur', 'Jodhpur', 'Kota'])}`,
    applicantPermanentAddress: `H.No ${randomIntBetween(1, 100)}, ${randomItem(['Green', 'Royal', 'Sunrise'])} Colony`,
    firmAddress: `Plot No ${randomIntBetween(1, 50)}, ${randomItem(['Mandi Road', 'Industrial Area', 'Agro Park'])}`,
    salePointAddress: `Shop No ${randomIntBetween(1, 20)}, ${randomItem(['Krishi Market', 'Farmer Plaza', 'Agri Complex'])}`,
    saleStorageAddress: `Warehouse ${randomIntBetween(1, 10)}, ${randomItem(['Outer Ring Road', 'Storage Zone', 'Logistics Park'])}`,
  };
}


export function setup() {
  console.log('Starting Rajasthan Seed Licensing Stress Test...');
  console.log(`Base URL: ${BASE_URL}`);

  const response = http.get(`${BASE_URL}/owner/`);
  if (response.status !== 200) {
    console.error('Failed to connect to API. Please check if the server is running.');
  } else {
    console.log('API connectivity confirmed.');
  }
}


export default function () {
  const isCitizen = randomIntBetween(0, 1) === 0;

  if (isCitizen) {

    group('Citizen: Submit License Application', () => {
      const payload = generateApplication();
      log(`Submitting new license application for ${payload.applicantName}`);
      const res = http.post(`${BASE_URL}/license/create/`, JSON.stringify(payload), JSON_HEADERS);
      if ([200, 201, 202].includes(res.status)) {
        stats.applicationsCreated++;
      } else {
        stats.applicationsFailed++;
      }
      check(res, { 'Application submitted successfully': (r) => [200, 201, 202].includes(r.status) });
      log(`Create response status: ${res.status}`);
      sleep(randomIntBetween(1, 3));
    });

  } else {

    group('Officer: Process Applications', () => {
      log('Fetching license count...');
      const countRes = http.get(`${BASE_URL}/license/count/`);
      check(countRes, { 'License count retrieved': (r) => r.status === 200 });
      const licenseCount = countRes.json().data;
      log(`Current license count: ${licenseCount}`);

      if (licenseCount > 0) {
        let licenseId = randomIntBetween(1, licenseCount);
        log(`Processing license ID: ${licenseId}`);
       
     
        const detailsRes = http.get(`${BASE_URL}/license/${licenseId}/info/`);
        check(detailsRes, { 'License details retrieved': (r) => r.status === 200 });
        log(`License details response status: ${detailsRes.status}`);

        if (detailsRes.status === 200) {
          const license = detailsRes.json().data;
          const terminalStatuses = ['APPROVED', 'REJECTED', 'REVOKED', 'EXPIRED'];

          if (license && !terminalStatuses.includes(license.status)) {
            const currentStatusIndex = statusFlow.findIndex(s => s.status === license.status);
            const nextStatus = statusFlow[currentStatusIndex + 1];
            if (!nextStatus) {
              log(`No valid next status for license ${licenseId}, skipping update.`);
              return;
            }

            const officer = randomItem(officerData);
            const updatePayload = {
              licenseId: licenseId,
              status: nextStatus.status,
              officerName: officer.name,
              role: officer.role,
              remarks: nextStatus.remarks
            };
            if (nextStatus.status === 'APPROVED') {
              updatePayload.renewalPeriodDays = nextStatus.renewalPeriodDays;
            }

            log(`Updating license ${licenseId} to status: ${nextStatus.status}`);
            const updateRes = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(updatePayload), JSON_HEADERS);
            if (updateRes.status === 200) {
              stats.statusUpdates++;
            } else {
              stats.statusUpdateFails++;
            }
            check(updateRes, { 'Status updated successfully': (r) => r.status === 200 });
            log(`Update response status: ${updateRes.status}`);

            if (nextStatus.status === 'APPROVED') {
              log(`Fetching QR for license ${licenseId}`);
              const qrRes = http.get(`${BASE_URL}/license/${licenseId}/qr/`);
              check(qrRes, { 'QR data retrieved': (r) => r.status === 200 });

              if (qrRes.status === 200) {
                const qrData = qrRes.json();
                log(`Verifying license ${qrData.licenseNumber} with hash ${qrData.verificationHash}`);
                const verifyRes = http.post(
                  `${BASE_URL}/license/verify/`,
                  JSON.stringify({ licenseNumber: qrData.licenseNumber, expectedHash: qrData.verificationHash }),
                  JSON_HEADERS
                );
                if (verifyRes.status === 200) {
                  stats.verifications++;
                } else {
                  stats.verificationFails++;
                }
                check(verifyRes, { 'License verified successfully': (r) => r.status === 200 });
                log(`Verify response status: ${verifyRes.status}`);
              }
            }
          }
        }
        sleep(randomIntBetween(1, 2));
      }
    });
  }
}