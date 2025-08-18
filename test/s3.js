import http from 'k6/http';
import { check, sleep, group, fail } from 'k6';
import { SharedArray } from 'k6/data';

// --- Configuration ---
const BASE_URL = 'http://127.0.0.1:8000/api/blockchain'; // Replace with your actual base URL

// --- Test Data ---
const newLicensePayload = {
  licenseCategory: "SEED",
  licenseLevel: "DISTRICT",
  registeringAuthority: "Department of Agriculture",
  registeringOfficeName: "District Agri Office, Jaipur",
  applicantName: "Ravi Kumar",
  aadhaarNumber: "123456789012",
  applicantPermanentAddress: "H.No 45, Green Colony, Jaipur",
  firmName: "Ravi Agro Traders",
  firmType: "Partnership",
  firmAddress: "Plot No 22, Mandi Road, Jaipur",
  salePointAddress: "Shop No 5, Krishi Market, Jaipur",
  saleStorageAddress: "Warehouse No 3, Outer Ring Road, Jaipur",
  cropName: "Wheat",
  cropVariety: "HD2967",
  isSeedSelfProduced: false,
  productionCompany: "Agro Seeds Pvt Ltd"
};

const officerDetails = {
    officerName: "Shrawan",
    role: "AGRICULTURE_OFFICER"
};

// Statuses in the required order of transition
const statusFlow = [
    "UNDER_REVIEW",
    "DOCUMENTS_VERIFIED",
    "INSPECTION_SCHEDULED",
    "INSPECTION_COMPLETED",
    "APPROVED"
];


// --- k6 Options for Load/Stress Testing ---
export const options = {
    // Stages define the load profile.
    // This example simulates a ramp-up, a sustained load, and a ramp-down.
    stages: [
        { duration: '30s', target: 5 },  // Ramp-up to 50 virtual users over 2 minutes
        { duration: '1m', target: 5 },  // Stay at 50 virtual users for 5 minutes (sustained load)
        { duration: '30s', target: 10 }, // Ramp-up to 100 virtual users over 1 minute (stress)
        { duration: '1m', target: 10 }, // Stay at 100 virtual users for 3 minutes
        { duration: '30s', target: 0 },   // Ramp-down to 0 users
    ],
    thresholds: {
        http_req_failed: ['rate<0.05'],   // http errors should be less than 5%
        http_req_duration: ['p(95)<5000'], // 95% of requests should be below 5000ms
    },
    timeout: '60s',
};

// --- Main Test Function ---
export default function () {
    let licenseId;
    let licenseNumber;
    let expectedHash;

    // --- Make test data unique for each iteration to simulate different users ---
    const uniqueAadhaar = `1234${Math.floor(10000000 + Math.random() * 90000000)}`;
    const uniqueFirmName = `${newLicensePayload.firmName} ${__VU}-${__ITER}`;
    const dynamicPayload = {
        ...newLicensePayload,
        aadhaarNumber: uniqueAadhaar,
        firmName: uniqueFirmName,
    };


    group('01. Pre-submission Checks', function () {
        // Check owner - should always be available
        const ownerRes = http.get(`${BASE_URL}/owner/`);
        check(ownerRes, { 'Owner endpoint is reachable': (r) => r.status === 200 });

        // Check license count - should always be available
        const countRes = http.get(`${BASE_URL}/license/count/`);
        check(countRes, { 'Count endpoint is reachable': (r) => r.status === 200 });
    });

    group('02. Submit New License Application', function () {
        const res = http.post(`${BASE_URL}/license/create/`, JSON.stringify(dynamicPayload), {
            headers: { 'Content-Type': 'application/json' },
        });

        const submissionCheck = check(res, {
            'License submitted successfully': (r) => r.status === 200 || r.status === 201,
            'Response contains licenseId': (r) => r.json('data.license_id') !== undefined,
        });

        if (!submissionCheck) {
            fail('License creation failed, aborting test.');
            return;
        }

        licenseId = res.json('data.license_id');
        console.log(`License created with ID: ${licenseId}`);
        sleep(1);
    });

    if (licenseId) {
        group('03. Verify Initial State', function () {
            const res = http.get(`${BASE_URL}/license/${licenseId}/info/`);
            check(res, {
                'Get license details is successful': (r) => r.status === 200,
                'Initial status is SUBMITTED': (r) => r.json('data.status') === 'SUBMITTED',
            });
             if(res.status === 200){
                licenseNumber = res.json('data.licenseNumber');
                console.log(`License Number: ${licenseNumber}`);
            }
        });

        group('04. License Status Progression', function () {
            for (const status of statusFlow) {
                sleep(1);
                const payload = {
                    licenseId: licenseId,
                    status: status,
                    officerName: officerDetails.officerName,
                    role: officerDetails.role,
                    remarks: `License is now ${status}`
                };

                if (status === 'APPROVED') {
                    payload.renewalPeriodDays = 365;
                }

                const res = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(payload), {
                    headers: { 'Content-Type': 'application/json' },
                });

                const statusUpdateCheck = check(res, {
                    [`Status successfully updated to ${status}`]: (r) => r.status === 200,
                });

                if (!statusUpdateCheck) {
                    fail(`Failed to update status to ${status}. Aborting VU.`);
                    return; 
                }
            }
        });

        group('05. Post-Approval API Calls', function () {
            const qrRes = http.get(`${BASE_URL}/license/${licenseId}/qr/`);
            check(qrRes, {
                'Get QR data is successful after approval': (r) => r.status === 200,
                'QR response contains expected hash': (r) => r.json('data.verificationHash') !== undefined,
            });
            if (qrRes.status === 200) {
                expectedHash = qrRes.json('data.verificationHash');
            }

            if (licenseNumber && expectedHash) {
                const verifyPayload = {
                    licenseNumber: licenseNumber,
                    expectedHash: expectedHash
                };
                const verifyRes = http.post(`${BASE_URL}/license/verify/`, JSON.stringify(verifyPayload), {
                    headers: { 'Content-Type': 'application/json' },
                });
                check(verifyRes, {
                    'License verification is successful': (r) => r.status === 200,
                });
            }

            const updatePayload = {
                license_id: licenseId,
                firm_name: "Ravi Agro Traders Updated",
                role: "JOINT_DIRECTOR"
            };
            const updateRes = http.post(`${BASE_URL}/license/update/`, JSON.stringify(updatePayload), {
                headers: { 'Content-Type': 'application/json' },
            });
            check(updateRes, {
                'Update license details is successful after approval': (r) => r.status === 200,
            });
        });

        group('06. Action History Check', function () {
            const historyRes = http.get(`${BASE_URL}/license/${licenseId}/history/`);
            check(historyRes, {
                'Get action history is successful': (r) => r.status === 200,
            });
        });
    }
}
