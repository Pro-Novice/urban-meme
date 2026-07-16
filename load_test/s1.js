import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';

// Configuration for different test phases
export const options = {
    stages: [
        // Ramp-up to 50 users over 1 minute
        { duration: '1m', target: 50 },
        // Stay at 50 users for 3 minutes
        { duration: '3m', target: 50 },
        // Spike to 100 users quickly
        { duration: '30s', target: 100 },
        // Maintain spike for 1 minute
        { duration: '2m', target: 100 },
        // Ramp-down to 0 users
        { duration: '1m', target: 0 },
    ],
    thresholds: {
        http_req_failed: ['rate<0.05'],    // Less than 5% failures
        http_req_duration: ['p(95)<5000'], // 95% requests < 5s
    },
    discardResponseBodies: false,
};

// Base configuration
const BASE_URL = 'http://127.0.0.1:8000/api/blockchain';

function randomIntBetween(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomItem(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

// Shared test data across VUs
const applicantData = new SharedArray('applicants', function () {
    return [
        {
            licenseCategory: 'SEED',
            applicationLicenseType: 'NEW_APPLICATION',
            licenseLevel: 'DISTRICT',
            applicantName: 'Ravi Kumar',
            aadhaarNumber: '123456789012',
            firmName: 'Ravi Agro Traders',
            firmType: 'Partnership',
            cropName: ['Wheat', 'Rice', 'Maize'],
            cropVariety: ['HD2967', 'IR64', 'Pioneer 30T90'],
            isSeedSelfProduced: false,
            productionCompany: 'Sharma Seeds Pvt Ltd'
        },
        {
            licenseCategory: 'SEED',
            applicationLicenseType: 'NEW_APPLICATION',
            licenseLevel: 'STATE',
            applicantName: 'Priya Sharma',
            aadhaarNumber: '987654321098',
            firmName: 'Sharma Seeds',
            firmType: 'Proprietorship',
            cropName: ['Rice'],
            cropVariety: ['PR126', 'Basmati-370', 'IR64'],
            isSeedSelfProduced: true,
            productionCompany: 'Sharma Seeds Pvt Ltd'
        },
        {
            licenseCategory: 'SEED',
            applicationLicenseType: 'NEW_APPLICATION',
            licenseLevel: 'DISTRICT',
            applicantName: 'Vijay Singh',
            aadhaarNumber: '564738291023',
            firmName: 'Vijay Agro',
            firmType: 'LLP',
            cropName: ['Maize'],
            cropVariety: ['PMH1', 'Pioneer 30T90', 'HM4'],
            isSeedSelfProduced: false,
            productionCompany: 'Sharma Seeds Pvt Ltd'
        }
    ];
});

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

// Generate random application data
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

// Main test function
export default function () {
    // Randomly decide if this VU is a citizen or officer
    const isCitizen = randomIntBetween(0, 1) === 0;

    if (isCitizen) {
        // Citizen workflow: Submit application
        group('Citizen: Submit License Application', function () {
            const payload = generateApplication();
            const res = http.post(
                `${BASE_URL}/license/create/`,
                JSON.stringify(payload),
                { headers: { 'Content-Type': 'application/json' } }
            );

            // status can be 200 or 201
            check(res, {
                'Application submitted successfully': (r) => r.status === 201 || r.status === 200 || r.status === 202
            });

            // Random sleep to simulate user think time
            sleep(randomIntBetween(1, 3));
        });
    } else {
        // Officer workflow: Process applications
        group('Officer: Process Applications', function () {
            // Step 1: Get license count
            const countRes = http.get(`${BASE_URL}/license/count/`);
            check(countRes, {
                'License count retrieved': (r) => r.status === 200
            });
            const licenseCount = countRes.json().data;

            if (licenseCount > 0) {
                // Step 2: Process random license
                const licenseId = randomIntBetween(1, licenseCount);

                // Step 3: Get license details
                const detailsRes = http.get(`${BASE_URL}/license/${licenseId}/info/`);
                check(detailsRes, {
                    'License details retrieved': (r) => r.status === 200
                });

                // if (detailsRes.status === 200) {
                //     const license = detailsRes.json().data;

                //     // Process next status if not terminal
                //     const terminalStatuses = ['APPROVED', 'REJECTED', 'REVOKED', 'EXPIRED'];
                //     if (!terminalStatuses.includes(license.status)) {
                //         const currentStatusIndex = statusFlow.findIndex(s => s.status === license.status);
                //         const nextStatus = statusFlow[currentStatusIndex + 1];

                //         // Step 4: Update license status
                //         const officer = randomItem(officerData);
                //         const updatePayload = {
                //             licenseId: licenseId,
                //             status: nextStatus.status,
                //             officerName: officer.name,
                //             role: officer.role,
                //             remarks: nextStatus.remarks
                //         };

                //         if (nextStatus.status === 'APPROVED') {
                //             updatePayload.renewalPeriodDays = nextStatus.renewalPeriodDays;
                //         }

                //         const updateRes = http.post(
                //             `${BASE_URL}/license/update-status/`,
                //             JSON.stringify(updatePayload),
                //             { headers: { 'Content-Type': 'application/json' } }
                //         );

                //         check(updateRes, {
                //             'Status updated successfully': (r) => r.status === 200
                //         });

                //         // Step 5: Additional actions for approved licenses
                //         if (nextStatus.status === 'APPROVED') {
                //             // Get QR data
                //             const qrRes = http.get(`${BASE_URL}/license/${licenseId}/qr/`);
                //             check(qrRes, {
                //                 'QR data retrieved': (r) => r.status === 200
                //             });

                //             // Log QR data
                //             console.log(`QR Data for License ID ${licenseId}: ${JSON.stringify(qrRes.json())}`);

                //             // Verify license integrity
                //             if (qrRes.status === 200) {
                //                 const verifyRes = http.post(
                //                     `${BASE_URL}/license/verify/`,
                //                     JSON.stringify({
                //                         licenseNumber: license.licenseNumber,
                //                         expectedHash: qrRes.data.verificationHash
                //                     }),
                //                     { headers: { 'Content-Type': 'application/json' } }
                //                 );
                //                 console.log(`License verification response: ${JSON.stringify(verifyRes.json())}`);
                //                 // check(verifyRes, {
                //                 //     'License verified successfully': (r) =>
                //                 //         r.status === 200 && r.json().valid === true
                //                 // });
                //             }
                //         }
                //     }
                // }

                // Random sleep between operations
                sleep(randomIntBetween(1, 2));
            }
        });
    }
}

export function setup() {
    console.log('Starting Rajasthan Seed Licensing API Test...');
    console.log(`Base URL: ${BASE_URL}`);

    // Test basic connectivity
    const response = http.get(`${BASE_URL}/owner/`);
    if (response.status !== 200) {
        console.error('Failed to connect to API. Please check if the server is running.');
    } else {
        console.log('API connectivity confirmed.');
    }
}
