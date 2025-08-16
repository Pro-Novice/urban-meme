import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';

// Test configuration
export let options = {
    stages: [
        { duration: '30s', target: 5 },   // Ramp up to 3 users (reduced load)
        { duration: '1m', target: 10 },    // Stay at 5 users
        { duration: '30s', target: 0 },   // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<5000'], // 95% of requests should be below 5s
        http_req_failed: ['rate<0.1'],     // Error rate should be below 20%
    },
    timeout: '60s',
};

// Base URL
const BASE_URL = 'http://127.0.0.1:8000/api/blockchain';

// Test data for license applications
let testData = new SharedArray('license applications', function () {
    return [
        {
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
        },
        {
            licenseCategory: "SEED",
            licenseLevel: "STATE",
            registeringAuthority: "Department of Agriculture",
            registeringOfficeName: "State Agri Office, Rajasthan",
            applicantName: "Sunita Sharma",
            aadhaarNumber: "987654321098",
            applicantPermanentAddress: "H.No 67, Blue Street, Udaipur",
            firmName: "Sharma Seeds Co",
            firmType: "Private Limited",
            firmAddress: "Building A, Industrial Area, Udaipur",
            salePointAddress: "Shop 12, Seed Market, Udaipur",
            saleStorageAddress: "Godown 5, RIICO Area, Udaipur",
            cropName: "Rice",
            cropVariety: "Basmati",
            isSeedSelfProduced: true,
            productionCompany: "Sharma Seeds Co"
        }
    ];
});

// Status progression order
const STATUS_PROGRESSION = [
    'SUBMITTED',
    'UNDER_REVIEW',
    'DOCUMENTS_VERIFIED',
    'INSPECTION_SCHEDULED',
    'INSPECTION_COMPLETED',
    'APPROVED'
];

export default function () {
    const userIndex = __VU - 1;
    const licenseData = { ...testData[userIndex % testData.length] };

    // Add unique identifiers to avoid conflicts between virtual users
    licenseData.applicantName = `${licenseData.applicantName} VU${__VU}`;
    licenseData.firmName = `${licenseData.firmName} VU${__VU}`;
    licenseData.aadhaarNumber = `${licenseData.aadhaarNumber.slice(0, -2)}${String(__VU).padStart(2, '0')}`;


    // 1. Submit license application
    const licenseId = submitLicenseApplication(licenseData);

    if (licenseId) {
        // 2. Get initial license count
        getLicenseCount();

        // 3. Process status changes in order
        processStatusChanges(licenseId);

        // // 5. Get license details after approval
        // getLicenseDetails(licenseId);

        // // 6. Get license action history
        // getLicenseActionHistory(licenseId);

        // // 7. Get QR data (only after approval)
        // getQRData(licenseId);

        // // 8. Verify license integrity
        // verifyLicenseIntegrity(licenseId);

        // // 9. Update license details (only after approval)
        // updateLicenseDetails(licenseId);
    }

    sleep(1);
}

function checkOwner() {
    console.log('Checking owner...');
    const response = http.get(`${BASE_URL}/owner/`);

    check(response, {
        'Owner check status is 200': (r) => r.status === 200,
    });

    if (response.status !== 200) {
        console.error('Owner check failed:', response.body);
    }
}

function getLicenseCount() {
    console.log('Getting license count...');
    const response = http.get(`${BASE_URL}/license/count/`);

    check(response, {
        'License count status is 200': (r) => r.status === 200,
    });

    let count = 0;
    if (response.status === 200) {
        try {
            const data = JSON.parse(response.body);
            count = data.data;
            console.log(`Current license count: ${count}`);
        } catch (e) {
            console.error('Failed to parse license count response');
        }
    }

    return count;
}

function submitLicenseApplication(licenseData) {
    console.log('Submitting license application...');

    const payload = JSON.stringify(licenseData);
    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const response = http.post(`${BASE_URL}/license/create/`, payload, params);

    check(response, {
        'License submission status is 200 or 201': (r) => [200, 201].includes(r.status),
        'License submission response has license_id': (r) => {
            try {
                const data = JSON.parse(r.body);
                return data.license_id !== undefined;
            } catch {
                return false;
            }
        },
    });

    let licenseId = null;
    if ([200, 201].includes(response.status)) {
        try {
            const data = JSON.parse(response.body);
            licenseId = data.data.license_id;
            console.log(`License created with ID: ${licenseId}`);
        } catch (e) {
            console.error('Failed to parse license creation response:', response.body);
        }
    } else {
        console.error('License submission failed:', response.body);
    }

    return licenseId;
}

function processStatusChanges(licenseId) {
    console.log(`Processing status changes for license ${licenseId}...`);

    // Track current status to ensure proper progression
    let currentStatus = 'SUBMITTED';

    // Start from index 1 since SUBMITTED is the initial status
    for (let i = 1; i < STATUS_PROGRESSION.length; i++) {
        const nextStatus = STATUS_PROGRESSION[i];

        // Update status and check if successful
        const success = updateLicenseStatus(licenseId, nextStatus, currentStatus);

        if (success) {
            currentStatus = nextStatus;
            console.log(`Successfully updated license ${licenseId} to ${nextStatus}`);
            sleep(1); // Longer delay between status updates to avoid timeouts
        } else {
            console.error(`Failed to update license ${licenseId} to ${nextStatus}. Stopping status progression.`);
            break; // Stop progression if update fails
        }
    }

    return currentStatus;
}

function updateLicenseStatus(licenseId, status) {
    console.log(`Updating license ${licenseId} status to ${status}...`);

    const payload = {
        licenseId: licenseId,
        status: status,
        officerName: "Test Officer",
        role: "AGRICULTURE_OFFICER",
        remarks: `License status updated to ${status}`
    };

    // Add renewal period for APPROVED status
    if (status === 'APPROVED') {
        payload.renewalPeriodDays = 365; // 1 year
    }

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const response = http.post(`${BASE_URL}/license/update-status/`, JSON.stringify(payload), params);

    check(response, {
        [`Status update to ${status} successful`]: (r) => [200, 201].includes(r.status),
    });

    if (![200, 201].includes(response.status)) {
        console.error(`Failed to update status to ${status}:`, response.body);
    }
}

function getLicenseDetails(licenseId) {
    console.log(`Getting details for license ${licenseId}...`);

    const response = http.get(`${BASE_URL}/license/${licenseId}/info/`);

    check(response, {
        'License details status is 200': (r) => r.status === 200,
        'License details response has license data': (r) => {
            try {
                const data = JSON.parse(r.body);
                return data.license_id !== undefined;
            } catch {
                return false;
            }
        },
    });

    if (response.status !== 200) {
        console.error('Failed to get license details:', response.body);
    }
}

function getLicenseActionHistory(licenseId) {
    console.log(`Getting action history for license ${licenseId}...`);

    const response = http.get(`${BASE_URL}/license/${licenseId}/history/`);

    check(response, {
        'License history status is 200': (r) => r.status === 200,
        'License history response has actions': (r) => {
            try {
                const data = JSON.parse(r.body);
                return Array.isArray(data) || data.actions !== undefined;
            } catch {
                return false;
            }
        },
    });

    if (response.status !== 200) {
        console.error('Failed to get license history:', response.body);
    }
}

function getQRData(licenseId) {
    console.log(`Getting QR data for license ${licenseId}...`);

    const response = http.get(`${BASE_URL}/license/${licenseId}/qr/`);

    check(response, {
        'QR data status is 200': (r) => r.status === 200,
        'QR data response has qr information': (r) => {
            try {
                const data = JSON.parse(r.body);
                return data.qr_data !== undefined || data.qr_code !== undefined;
            } catch {
                return false;
            }
        },
    });

    if (response.status !== 200) {
        console.error('Failed to get QR data:', response.body);
    }
}

function verifyLicenseIntegrity(licenseId) {
    console.log(`Verifying integrity for license ${licenseId}...`);

    // First get the license details to extract license number and hash
    const detailsResponse = http.get(`${BASE_URL}/license/${licenseId}/info/`);

    if (detailsResponse.status === 200) {
        try {
            const licenseData = JSON.parse(detailsResponse.body);
            const licenseNumber = licenseData.license_number;
            const expectedHash = licenseData.hash; // Assuming hash is in the response

            if (licenseNumber) {
                const payload = {
                    licenseNumber: licenseNumber,
                    expectedHash: expectedHash || "sample_hash_for_testing"
                };

                const params = {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                };

                const response = http.post(`${BASE_URL}/license/verify/`, JSON.stringify(payload), params);

                check(response, {
                    'License verification status is 200': (r) => r.status === 200,
                });

                if (response.status !== 200) {
                    console.error('License verification failed:', response.body);
                }
            }
        } catch (e) {
            console.error('Failed to parse license details for verification:', e);
        }
    }
}

function updateLicenseDetails(licenseId) {
    console.log(`Updating details for license ${licenseId}...`);

    const payload = {
        license_id: licenseId,
        firm_name: "Updated Firm Name",
        firm_type: "Updated Partnership",
        crop_variety: "Updated Variety",
        role: "JOINT_DIRECTOR"
    };

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const response = http.post(`${BASE_URL}/license/update/`, JSON.stringify(payload), params);

    check(response, {
        'License details update status is 200': (r) => r.status === 200,
    });

    if (response.status !== 200) {
        console.error('Failed to update license details:', response.body);
    }
}

// Setup function to run before the test starts
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

// Teardown function to run after the test completes
export function teardown(data) {
    console.log('Test completed.');
}