"""
Django settings for config project.
"""

from pathlib import Path
from decouple import config
from web3 import Web3
from django.core.exceptions import ImproperlyConfigured
import os, json, logging
from hexbytes import HexBytes
from django.core.serializers.json import DjangoJSONEncoder

# ================== BASE CONFIG ================== #
BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ================== SECURITY ================== #
SECRET_KEY = config('SECRET_KEY')
DJANGO_ENV = config("DJANGO_ENV", default="development")

if DJANGO_ENV == "production":
    DEBUG = False
    ALLOWED_HOSTS = ['10.70.233.251', 'localhost']
else:
    DEBUG = True
    ALLOWED_HOSTS = ["*"]

# ================== APPLICATIONS ================== #
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'apps.seed_licenses',
    'drf_spectacular',
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'djangorestframework_camel_case.render.CamelCaseJSONRenderer',
        'djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'djangorestframework_camel_case.parser.CamelCaseJSONParser',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ================== SPECTACULAR (API DOCS) ================== #
SPECTACULAR_SETTINGS = {
    'TITLE': 'Rajasthan Agriculture License System API',
    'DESCRIPTION': 'Blockchain-based license management',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CAMELIZE_NAMES': True,  
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/',
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
    'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': False,
}

# ================== MIDDLEWARE ================== #
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ================== LOGGING ================== #
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
        'simple': {'format': '{levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
        'apps.seed_licenses': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'blockchain': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ================== DATABASE ================== #
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB'),
        'USER': config('POSTGRES_USER'),
        'PASSWORD': config('POSTGRES_PASSWORD'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}


# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache', 
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient', 
#         },
#         'KEY_PREFIX': 'agri_license',  
#         'TIMEOUT': 1800, 
#     }
# }


# ================== AUTH ================== #
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
import os, json, logging
from hexbytes import HexBytes
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger("blockchain")
# ================== I18N ================== #
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================== BLOCKCHAIN CONFIG ================== #
RAW_RPC_URLS = config("RPC_URLS", default="http://127.0.0.1:8545/")
RPC_URLS = [url.strip() for url in RAW_RPC_URLS.split(",") if url.strip()]
BLOCKCHAIN_URL = RPC_URLS[0] if RPC_URLS else "http://127.0.0.1:8545/"

CHAIN_ID = config("CHAIN_ID", default=1337, cast=int)
PRIVATE_KEY = config("PRIVATE_KEY", default=None)
CONTRACT_ADDRESS = config("CONTRACT_ADDRESS", default="")

RAW_PRIVATE_KEYS = config("PRIVATE_KEYS", default="")
RAW_CONTRACT_ADDRESSES = config("CONTRACT_ADDRESSES", default="")

# Parse multiple private keys and addresses
PRIVATE_KEYS = [key.strip() for key in RAW_PRIVATE_KEYS.split(",") if key.strip()]
CONTRACT_ADDRESSES = [addr.strip() for addr in RAW_CONTRACT_ADDRESSES.split(",") if addr.strip()]

# Validate that private keys and addresses have matching counts
if PRIVATE_KEYS and CONTRACT_ADDRESSES:
    if len(PRIVATE_KEYS) != len(CONTRACT_ADDRESSES):
        logger.warning(f"⚠️ Mismatch: {len(PRIVATE_KEYS)} private keys vs {len(CONTRACT_ADDRESSES)} addresses")
    else:
        logger.info(f"✅ Loaded {len(PRIVATE_KEYS)} private key-address pairs from environment")

# Derive default wallet address from single PRIVATE_KEY (backward compatibility)
if PRIVATE_KEY:
    WALLET_ADDRESS = Web3().eth.account.from_key(PRIVATE_KEY).address
elif PRIVATE_KEYS:
    # Use first private key as default for backward compatibility
    PRIVATE_KEY = PRIVATE_KEYS[0]
    WALLET_ADDRESS = Web3().eth.account.from_key(PRIVATE_KEYS[0]).address
else:
    raise ImproperlyConfigured("No PRIVATE_KEY or PRIVATE_KEYS found in environment variables.")

# Optional: main contract address for decoding
BESU_CONTRACT_ADDRESS = config("BESU_CONTRACT_ADDRESS", default="")

# ================== CELERY CONFIG ================== #
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# ================== CRYPTOGRAPHY KEYS ================== #
try:
    PRIVATE_KEY_PATH = BASE_DIR / 'private_key.pem'
    PUBLIC_KEY_PATH = BASE_DIR / 'public_key.pem'
    GENERATED_PRIVATE_KEY_BYTES = PRIVATE_KEY_PATH.read_bytes()
    GENERATED_PUBLIC_KEY = PUBLIC_KEY_PATH.read_text()
except FileNotFoundError:
    raise ImproperlyConfigured("Key files (private_key.pem or public_key.pem) not found in project root.")

# ================== CONTRACT ABI PATH & JSON SERIALIZER ================== #


# Primary & fallback paths
PRIMARY_DEPLOYMENT_PATH = BASE_DIR / "blockchain" / "deployment_info.json"
FALLBACK_ABI_PATH = BASE_DIR / "blockchain" / "artifacts" / "contracts" / "LicenseSystemV1.sol" / "LicenseSystemV1.json"

# Load from .env or use primary as default
CONTRACT_ABI_PATH = config(
    "CONTRACT_ABI_PATH",
    default=str(PRIMARY_DEPLOYMENT_PATH)
)

def detect_and_load_contract_file(path):
    """Detect contract file type (deployment_info or Hardhat ABI) and load JSON."""
    if not os.path.exists(path):
        logger.warning(f"[WARN] Contract file not found: {path}")
        return None, None

    try:
        with open(path, "r") as f:
            data = json.load(f)

        # Case 1: deployment_info.json format
        if "implementations" in data and "proxy" in data:
            proxy = data.get("proxy")
            current_impl = data.get("currentImplementation", "Unknown")
            logger.info(f"[INFO] ✅ Loaded deployment_info.json (Proxy: {proxy}, Impl: {current_impl})")
            return "deployment_info", data

        # Case 2: Hardhat artifact format
        elif "abi" in data and "contractName" in data:
            logger.info(f"[INFO] ✅ Loaded Hardhat artifact for {data['contractName']}")
            return "hardhat_abi", data

        else:
            logger.warning(f"[WARN] Unknown JSON structure in {path}")
            return "unknown", data

    except Exception as e:
        logger.error(f"[ERROR] Failed to read {path}: {e}")
        return None, None


# Try loading primary deployment_info.json
file_type, abi_data = detect_and_load_contract_file(CONTRACT_ABI_PATH)

# Fallback to Hardhat artifact if necessary
if not abi_data:
    logger.warning(f"[FALLBACK] Using Hardhat artifact at: {FALLBACK_ABI_PATH}")
    file_type, abi_data = detect_and_load_contract_file(FALLBACK_ABI_PATH)
    CONTRACT_ABI_PATH = str(FALLBACK_ABI_PATH)

# Log result
if abi_data:
    if file_type == "deployment_info":
        logger.info(f"[INFO] Using Deployment Info file: {CONTRACT_ABI_PATH}")
    elif file_type == "hardhat_abi":
        logger.info(f"[INFO] Using Hardhat ABI file: {CONTRACT_ABI_PATH}")
else:
    logger.warning("[WARN] ⚠️ No valid contract ABI file found. Blockchain decoding may fail.")

# ---- Fix HexBytes serialization globally ---- #
class DjangoHexJSONEncoder(json.JSONEncoder):
    """Fixes HexBytes / bytes / Web3 datatypes for JSON serialization."""
    def default(self, obj):
        from web3.datastructures import AttributeDict
        if isinstance(obj, HexBytes):
            return obj.hex()
        elif isinstance(obj, bytes):
            return obj.hex()
        elif isinstance(obj, AttributeDict):
            return dict(obj)
        elif isinstance(obj, set):
            return list(obj)
        return super().default(obj)

# Apply globally
DjangoJSONEncoder.default = DjangoHexJSONEncoder.default
logger.info("✅ Global HexBytes JSON encoder active.")
