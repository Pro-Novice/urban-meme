# 🌿 Rajasthan Seed Licensing Stress Testing Suite

This repository provides a **comprehensive stress-testing setup** for the **Blockchain-Integrated License Management System** using both **Locust (Python)** and **k6 (JavaScript)**.
It includes automatic **Aadhaar encryption**, **adaptive wait logic**, **smart retry handling**, and **HTML reporting**.

---

## 📁 Project Structure

```
project_root/
├── stress_test/
│   ├── locustfile.py              # Locust test script
│   ├── stress-test.js             # k6 performance test script
│   ├── run_test.sh                # Helper script to execute tests
│   ├── locust_report.html         # Auto-generated Locust HTML report
│   ├── stress_report.html         # Auto-generated k6 HTML report
│   ├── encrypted_aadhaar.json     # Generated Aadhaar data (encrypted)
│   └── .env                       # Environment variables (optional)
│
└── utils/
    └── encrypt_aadhaar.py         # Aadhaar encryption utility
```

---

## ⚙️ 1. Prerequisites

Ensure the following are installed:

| Tool             | Version | Command                                                           |
| ---------------- | ------- | ----------------------------------------------------------------- |
| **Python**       | ≥ 3.9   | `python3 --version`                                               |
| **pip**          | latest  | `pip install --upgrade pip`                                       |
| **Node.js**      | ≥ 18.x  | `node -v`                                                         |
| **Locust**       | ≥ 2.25  | `pip install locust`                                              |
| **k6**           | latest  | [Install guide](https://k6.io/docs/getting-started/installation/) |
---

## 🔐 2. Aadhaar Encryption Setup

### Step 1 — Place the public key

Ensure your Django app has a valid **public key** file path configured at:

```python
settings.PUBLIC_KEY_PATH = "path/to/public_key.pem"
```

### Step 2 — Run the encryption script

Generate encrypted Aadhaar numbers for testing:

```bash
python utils/encrypt_aadhaar.py
```

✅ Output:

```
✅ Encrypted Aadhaar numbers saved to: stress_test/encrypted_aadhaar.json
```

---

## 🚀 3. Locust Stress Test

### Step 1 — Navigate to the test folder

```bash
cd stress_test
```

## 🧠 4. Automated Bash Runner 

Use the included shell script to automate everything:

```bash
bash stress_test/run_test.sh
```

This script:

1. Encrypts Aadhaar numbers
2. Runs the Locust test in headless mode
3. Generates the HTML report automatically

---

## 🧾 5. Reports

| Type                       | Tool           | Output                   |
| -------------------------- | -------------- | ------------------------ |
| **Stress Test (Python)**   | Locust         | `locust_report.html`     |
| **Load Test (JS)**         | k6             | `stress_report.html`     |
| **Encrypted Aadhaar Data** | Python Utility | `encrypted_aadhaar.json` |

---

## 🧩 6. Environment Configuration

You can create a `.env` file under `stress_test/` for dynamic configuration:

```
BASE_URL=example_base_url

```

---

## 🧰 7. Troubleshooting

| Issue                          | Solution                                                                  |
| ------------------------------ | ------------------------------------------------------------------------- |
| ⚠️ `Public key file not found` | Verify `settings.PUBLIC_KEY_PATH` in Django settings.                     |
| ❌ `Backend not reachable`      | Ensure Django server is running before starting Locust or k6.             |
| 🕐 `Timeout errors`            | Reduce number of users or increase wait time in test scripts.             |
| ⚠️ `gas limit exceeded`        | Smart retry with exponential backoff already built in — no action needed. |

---

## 🏁 8. Summary

✅ **Locust** handles adaptive, realistic stress scenarios
✅ **k6** provides pure load testing metrics and threshold control
✅ **encrypt_aadhaar.py** ensures realistic secure test data
✅ **HTML reports** offer clear visual insights

---
