import os
import sys
import re
from typing import List
from pydantic import BaseModel, Field

# Only load .env file in development mode (Issue #1)
# In production, environment variables must be set by the deployment platform.
if os.getenv("ENV", "development") != "production":
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

class Settings(BaseModel):
    PROJECT_NAME: str = "InsightForge AI"
    API_V1_STR: str = "/api/v1"
    
    ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str
    GROQ_API_KEY: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    AES_KEY: str
    AES_KEYS: str = "{}"
    ACTIVE_AES_KEY_VERSION: str = "v1"
    FRONTEND_ORIGINS: List[str] = []

    model_config = {
        "frozen": True
    }

# 1. Read environment variables
env = os.getenv("ENV", "development")
db_url = os.getenv("DATABASE_URL", "")
groq_key = os.getenv("GROQ_API_KEY", "")
jwt_secret = os.getenv("JWT_SECRET_KEY", "")
jwt_algo = os.getenv("JWT_ALGORITHM", "HS256")
token_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
aes_key = os.getenv("AES_KEY", "")
aes_keys_raw = os.getenv("AES_KEYS", "")
active_aes_version = os.getenv("ACTIVE_AES_KEY_VERSION", "v1")
origins_raw = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000")

# Parse origins
origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

# 2. Strict Startup Validation
errors = []

if not db_url:
    errors.append("DATABASE_URL is missing or empty.")

if not groq_key:
    errors.append("GROQ_API_KEY is missing or empty.")

# Validate JWT Secret (SEC-002)
if not jwt_secret:
    errors.append("JWT_SECRET_KEY is missing or empty.")
elif len(jwt_secret) < 32:
    errors.append("JWT_SECRET_KEY is too weak: must be at least 32 characters in length.")
elif jwt_secret in ["mock-secret-key-mock-secret-key-mock-secret-key-12", "development-secret", "secret", "change_me"]:
    errors.append("JWT_SECRET_KEY uses a known default or insecure mock value.")

# Validate AES Key and Rotation (SEC-003, SEC-008)
import json
aes_keys_map = {}
if aes_keys_raw:
    try:
        aes_keys_map = json.loads(aes_keys_raw)
        if not isinstance(aes_keys_map, dict):
            errors.append("AES_KEYS is invalid: must be a JSON dictionary mapping version tags to keys.")
        else:
            for k, v in aes_keys_map.items():
                if not re.match(r"^[0-9a-fA-F]{64}$", v):
                    errors.append(f"AES_KEYS version '{k}' is invalid: must be a cryptographically secure 64-character hexadecimal string representing exactly 32 bytes.")
    except Exception as e:
        errors.append(f"AES_KEYS is invalid JSON: {e}")
else:
    if aes_key:
        if not re.match(r"^[0-9a-fA-F]{64}$", aes_key):
            errors.append("AES_KEY is invalid: must be a cryptographically secure 64-character hexadecimal string representing exactly 32 bytes.")
        else:
            aes_keys_map = {"v1": aes_key}
            aes_keys_raw = '{"v1": "' + aes_key + '"}'
    else:
        errors.append("Both AES_KEY and AES_KEYS are missing or empty.")

if aes_keys_map and active_aes_version not in aes_keys_map:
    errors.append(f"ACTIVE_AES_KEY_VERSION '{active_aes_version}' not found in configured AES_KEYS.")

# Validate CORS Wildcard in Production (SEC-004)
if env == "production":
    if not origins:
        errors.append("FRONTEND_ORIGINS is empty. Production mode requires explicitly configured allowed origins.")
    elif "*" in origins:
        errors.append("FRONTEND_ORIGINS contains wildcard '*' in production mode. Permissive wildcard origins are blocked.")

# 3. Halt Startup on Configuration Failure
if errors:
    print("\n" + "="*80)
    print("CRITICAL CONFIGURATION ERROR: Startup aborted due to configuration validation failures.")
    print("Please fix the following issues in your environment / .env file:")
    for idx, err in enumerate(errors, 1):
        print(f" {idx}. [FAIL] {err}")
    print("="*80 + "\n")
    sys.exit(1)

# Derive DEBUG (forced False in production, defaults True in development)
debug_flag = os.getenv("DEBUG", "true" if env != "production" else "false").lower() in ("true", "1", "yes")
if env == "production":
    debug_flag = False

# Instantiated settings
settings = Settings(
    ENV=env,
    DEBUG=debug_flag,
    DATABASE_URL=db_url,
    GROQ_API_KEY=groq_key,
    JWT_SECRET_KEY=jwt_secret,
    JWT_ALGORITHM=jwt_algo,
    ACCESS_TOKEN_EXPIRE_MINUTES=token_expire,
    AES_KEY=aes_key,
    AES_KEYS=aes_keys_raw,
    ACTIVE_AES_KEY_VERSION=active_aes_version,
    FRONTEND_ORIGINS=origins
)
