from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate our key
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=1024,
)

# Serialize private key
pem_private_key = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption() # For production, we can use an algo
)

# Serialize public key
public_key = private_key.public_key()
pem_public_key = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

with open('private_key.pem', 'wb') as f:
    f.write(pem_private_key)

with open('public_key.pem', 'wb') as f:
    f.write(pem_public_key)