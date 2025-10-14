import os
import sys
import json
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

# SETUP DJANGO ENVIRONMENT
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
from django.conf import settings
django.setup()

# ENCRYPTION FUNCTION (MATCHES SERIALIZER LOGIC)
def encrypt_aadhaar(aadhaar_number: str) -> str:
    try:
  
        public_key_path = settings.PUBLIC_KEY_PATH
        if not os.path.exists(public_key_path):
            raise FileNotFoundError(f"Public key file not found: {public_key_path}")

        with open(public_key_path, "rb") as key_file:
            public_key = serialization.load_pem_public_key(key_file.read())

        encrypted = public_key.encrypt(
            aadhaar_number.encode("utf-8"),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return base64.b64encode(encrypted).decode("utf-8")

    except Exception as e:
        print(f"Error encrypting Aadhaar {aadhaar_number}: {e}")
        return None

if __name__ == "__main__":
    aadhaar_numbers = ["289739751283", "234567890123", "345678901234"]

    encrypted_list = []
    for aadhaar in aadhaar_numbers:
        encrypted_value = encrypt_aadhaar(aadhaar)
        if encrypted_value:
            encrypted_list.append(encrypted_value)

    # Save output for stress test or Postman
    output_path = os.path.join(BASE_DIR, "stress_test", "encrypted_aadhaar.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(encrypted_list, f, indent=2)

    print(f"✅ Encrypted Aadhaar numbers saved to: {output_path}")
