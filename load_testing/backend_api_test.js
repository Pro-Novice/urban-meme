import http from 'k6/http';
import { check, sleep } from 'k6';

// Options: number of virtual users and duration
export const options = {
  vus: 100,         // number of virtual users
  duration: '1m',  // total test duration
};

// Helper function: random string
function randomString(length = 6){
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

// Helper function: random Aadhaar-like number
function randomAadhaar() {
  return Math.floor(100000000000 + Math.random() * 899999999999).toString();
}

// Base URL
const BASE_URL = 'http://10.70.233.251:8000';

export default function () {
  // 1. Check owner
  http.get(`${BASE_URL}/api/blockchain/owner/`);

  // 3. License count
  http.get(`${BASE_URL}/api/blockchain/license/count/`);

  // 4. Submit license application
  const licensePayload = {
    license_category: 'SEED',
    license_level: 'STATE',
    registering_authority: 'JOINT_DIRECTOR',
    registering_office_name: 'Office ' + randomString(),
    applicant_name: 'User ' + randomString(),
    aadhaar_number: randomAadhaar(),
    applicant_permanent_address: 'Address ' + randomString(),
    firm_name: 'Firm ' + randomString(),
    firm_type: 'LLP',
    firm_address: 'Firm Addr ' + randomString(),
    sale_point_address: 'Sale Addr',
    sale_storage_address: 'Storage Addr',
    production_company: 'Company X',
    crop_name: 'Wheat',
    crop_variety: 'Golden',
  };
  let res = http.post(`${BASE_URL}/api/blockchain/license/create/`, JSON.stringify(licensePayload), {
     headers: { 'Content-Type': 'application/json' },
  });
	check(res, {
		'status is 200': (r) => r.status === 200
}) || console.log(`FAILED ${res.status} - ${res.body}`);

  // 5. Verify license document
  const verifyPayload = {
    license_number: '1',
    expected_hash: 'dummyhashvalue123456789',
  };
  // http.post(`${BASE_URL}/api/blockchain/license/verify/`, JSON.stringify(verifyPayload), {
    // headers: { 'Content-Type': 'application/json' },
 //  });

  // 6. Update license details
  const updatePayload = {
    license_id: 1,
    firm_name: 'Updated Firm',
    firm_type: 'PVT',
    firm_address: 'Updated Addr',
    sale_point_address: 'Updated Sale',
    sale_storage_address: 'Updated Storage',
    production_company: 'Updated Co',
    crop_name: 'Corn',
    crop_variety: 'Sweet',
    role: 'JOINT_DIRECTOR',
  };
 //  http.post(`${BASE_URL}/api/blockchain/license/update/`, JSON.stringify(updatePayload), {
    // headers: { 'Content-Type': 'application/json' },
  // });

  // 7. Get license info/history/QR
  const licenseId = Math.floor(Math.random() * 5) + 1;
  // http.get(`${BASE_URL}/api/blockchain/license/${licenseId}/info/`);
  // http.get(`${BASE_URL}/api/blockchain/license/${licenseId}/history/`);
  // http.get(`${BASE_URL}/api/blockchain/license/${licenseId}/qr/`);

  // 8. Update license status
  const statusPayload = {
    license_id: 1,
    status: 'APPROVED',
    remarks: 'All documents verified.',
    officer_name: 'Officer X',
    role: 'JOINT_DIRECTOR',
    renewal_period_days: 365,
  };
  // http.post(`${BASE_URL}/api/blockchain/license/update-status/`, JSON.stringify(statusPayload), {
   // headers: { 'Content-Type': 'application/json' },
  // });

  // 9. Get transaction status
  const txHash = '0x' + Array.from({ length: 64 }, () => 'abcdef1234567890'[Math.floor(Math.random() * 16)]).join('');
  // http.get(`${BASE_URL}/api/blockchain/transaction/${txHash}/`);

  // 10. Contract info
  //http.get(`${BASE_URL}/api/blockchain/contract/LicenseSystemV1/address/`);
 //  http.get(`${BASE_URL}/api/blockchain/contract/LicenseSystemV1/methods/`);
 // http.get(`${BASE_URL}/api/blockchain/contract/LicenseSystemV1/abi/`);

  // Wait between tasks to simulate real users
  sleep(Math.random() * 2 + 1); // random sleep between 1-3s
}
