import logging
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR
from utils.api_response import ApiResponse
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# ✅ 1️⃣ Public Key Endpoint
@api_view(["GET"])
def get_public_key(request):
    """Return the public key for client-side encryption."""
    try:
        public_key = settings.GENERATED_PUBLIC_KEY
        if not public_key:
            raise ValueError("Public key not loaded from settings.")
        return ApiResponse(data={"public_key": public_key}, status=HTTP_200_OK)
    except Exception as e:
        logger.exception("Failed to retrieve public key")
        return ApiResponse(err=f"Error fetching public key: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ 2️⃣ Security Health Check Endpoint
@api_view(["GET"])
def security_health_check(request):
    """Check presence and validity of private/public keypair."""
    try:
        private_key_path = settings.BASE_DIR / "private_key.pem"
        public_key_path = settings.BASE_DIR / "public_key.pem"

        if not private_key_path.exists() or not public_key_path.exists():
            return ApiResponse(
                err="Missing one or both key files.",
                data={
                    "private_key_exists": private_key_path.exists(),
                    "public_key_exists": public_key_path.exists(),
                },
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )

        private_bytes = private_key_path.read_bytes()
        public_bytes = public_key_path.read_bytes()

        private_key = serialization.load_pem_private_key(
            private_bytes, password=None, backend=default_backend()
        )
        public_key = serialization.load_pem_public_key(
            public_bytes, backend=default_backend()
        )

        if not isinstance(private_key, rsa.RSAPrivateKey) or not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Invalid RSA key format.")

        priv_n = private_key.private_numbers().public_numbers.n
        pub_n = public_key.public_numbers().n

        valid = priv_n == pub_n

        return ApiResponse(
            data={
                "private_key_exists": True,
                "public_key_exists": True,
                "is_valid_rsa_keypair": valid,
            },
            status=HTTP_200_OK if valid else HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.exception("Security health check failed")
        return ApiResponse(err=f"Security health check failed: {str(e)}", status=HTTP_500_INTERNAL_SERVER_ERROR)
