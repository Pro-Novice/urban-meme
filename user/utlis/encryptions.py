from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import os
import base64
import jwt
import bcrypt

class RSAEncryption:
    def __init__(self):
        self.private_key = None
        self.public_key = None
        self._load_or_generate_keys()

    def _load_or_generate_keys(self):
        keys_dir = 'keys'
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
        public_key_path = os.path.join(keys_dir, 'public_key.pem')

        if not os.path.exists(keys_dir):
            os.makedirs(keys_dir)

        if not os.path.exists(private_key_path) or not os.path.exists(public_key_path):
            # Generate new key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            public_key = private_key.public_key()

            # Save private key
            with open(private_key_path, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # Save public key
            with open(public_key_path, 'wb') as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))

        # Load keys
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )

        with open(public_key_path, 'rb') as f:
            self.public_key = serialization.load_pem_public_key(
                f.read()
            )

    def encrypt_data(self, data: str) -> str:
        """Encrypt data using RSA"""
        if data is None:
            return ''

        encrypted = self.public_key.encrypt(
            data.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data using RSA"""
        decoded_data = base64.b64decode(encrypted_data.encode())
        decrypted = self.private_key.decrypt(
            decoded_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted.decode()

    @staticmethod
    def hash_data(data: str) -> str:
        """Hash data using bcrypt"""
        return bcrypt.hashpw(data.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_hash(data: str, hashed: str) -> bool:
        """Verify hashed data"""
        return bcrypt.checkpw(data.encode(), hashed.encode())