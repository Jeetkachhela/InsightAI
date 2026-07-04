import os
import re
import time
import base64
import sqlparse
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple, Dict, List
from jose import jwt, JWTError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings
from app.core.logging import logger
import bcrypt

# Password Hashing Setup
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

# JWT Auth Setup
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, jti: Optional[str] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    import uuid
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": "insightforge-auth",
        "aud": "insightforge-app",
        "jti": jti or str(uuid.uuid4())
    })
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None, jti: Optional[str] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=7)
        
    import uuid
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": "insightforge-auth",
        "aud": "insightforge-app",
        "jti": jti or str(uuid.uuid4())
    })
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM],
            audience="insightforge-app",
            issuer="insightforge-auth"
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT Token validation failed: {e}")
        return None

# AES-256 Credential Encryption
class CredentialEncryptor:
    def __init__(self, key_map: dict, active_version: str):
        self.key_map = {}
        for version_tag, hex_key in key_map.items():
            key_bytes = bytes.fromhex(hex_key)
            if len(key_bytes) != 32:
                raise ValueError(f"AES key version '{version_tag}' must be exactly 32 bytes.")
            self.key_map[version_tag] = AESGCM(key_bytes)
        self.active_version = active_version
        if active_version not in self.key_map:
            raise ValueError(f"Active key version '{active_version}' not found in key map.")

    def encrypt(self, plain_text: str) -> str:
        active_aes = self.key_map[self.active_version]
        nonce = os.urandom(12)  # GCM recommended nonce size
        encrypted_bytes = active_aes.encrypt(nonce, plain_text.encode(), None)
        result = nonce + encrypted_bytes
        b64_cipher = base64.b64encode(result).decode("utf-8")
        return f"{self.active_version}:{b64_cipher}"

    def decrypt(self, encrypted_base64: str) -> str:
        if ":" in encrypted_base64:
            parts = encrypted_base64.split(":", 1)
            version_tag = parts[0]
            cipher_part = parts[1]
            if version_tag in self.key_map:
                aes = self.key_map[version_tag]
                data = base64.b64decode(cipher_part)
                nonce = data[:12]
                cipher_text = data[12:]
                decrypted_bytes = aes.decrypt(nonce, cipher_text, None)
                return decrypted_bytes.decode("utf-8")

        # Fallback decrypt: try default version "v1" or active version
        fallback_tag = "v1" if "v1" in self.key_map else self.active_version
        aes = self.key_map[fallback_tag]
        data = base64.b64decode(encrypted_base64)
        nonce = data[:12]
        cipher_text = data[12:]
        decrypted_bytes = aes.decrypt(nonce, cipher_text, None)
        return decrypted_bytes.decode("utf-8")

# Instantiated encryptor
import json
try:
    _keys_map = json.loads(settings.AES_KEYS)
except Exception:
    _keys_map = {"v1": settings.AES_KEY}
    
encryptor = CredentialEncryptor(_keys_map, settings.ACTIVE_AES_KEY_VERSION)

def encrypt_credential(plain: str) -> str:
    return encryptor.encrypt(plain)

def decrypt_credential(encrypted: str) -> str:
    return encryptor.decrypt(encrypted)

# Deterministic SQL Firewall
# Block: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, GRANT, REVOKE, etc.
FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "truncate", "create", 
    "replace", "grant", "revoke", "into", "exec", "execute", "vacuum", 
    "analyze", "explain", "show", "set", "reset", "begin", "commit", 
    "rollback", "savepoint", "copy", "load", "declare", "fetch", "close"
}

FORBIDDEN_FUNCTIONS = [
    r"\bpg_read_file\b", r"\bpg_write_file\b", r"\bpg_ls_dir\b", 
    r"\bpg_execute_server_program\b", r"\blo_import\b", r"\blo_export\b",
    r"\bdblink\b", r"\bquery_to_xml\b", r"\bpg_sleep\b"
]

def is_safe_select_query(query: str) -> Tuple[bool, str]:
    """
    Deterministically analyzes a SQL query to verify it is SELECT-only and contains no write operations.
    Strips comments before parsing to prevent bypasses, and checks for dangerous pg functions.
    """
    if not query or not query.strip():
        return False, "Query is empty."
        
    # Strip SQL comments (multi-line and single-line)
    clean_query = re.sub(r"/\*.*?\*/", "", query, flags=re.DOTALL)
    clean_query = re.sub(r"--.*?\n", "\n", clean_query)
    clean_query = clean_query.strip()
    
    if not clean_query:
        return False, "Query only contains comments."
        
    try:
        statements = sqlparse.parse(clean_query)
    except Exception as e:
        return False, f"Failed to parse SQL: {str(e)}"
        
    if not statements:
        return False, "No valid SQL statements found."
        
    if len(statements) > 1:
        return False, "Multi-statement queries (separated by semicolons) are blocked for security."
        
    stmt = statements[0]
    
    if stmt.get_type() != "SELECT":
        return False, f"Operation type '{stmt.get_type()}' is blocked. Only SELECT statements are permitted."
        
    query_lower = clean_query.lower()
    for pattern in FORBIDDEN_FUNCTIONS:
        if re.search(pattern, query_lower):
            return False, "Blocked function or database construct detected."
            
    # Check for PG catalog/system table access
    if re.search(r"\bpg_[a-zA-Z0-9_]+\b", query_lower) or "information_schema" in query_lower:
        blocked_catalogs = ["pg_shadow", "pg_authid", "pg_user", "pg_proc", "pg_namespace", "pg_database", "pg_tablespace", "pg_roles"]
        for cat in blocked_catalogs:
            if cat in query_lower:
                return False, f"Access to system catalog table '{cat}' is blocked."
                
    # Recursive token scan
    def check_tokens(tokens):
        for token in tokens:
            if token.is_group:
                safe, msg = check_tokens(token.tokens)
                if not safe:
                    return False, msg
            else:
                val = str(token.value).lower().strip()
                ttype = token.ttype
                
                if ttype in sqlparse.tokens.Keyword or ttype in sqlparse.tokens.DML or ttype in sqlparse.tokens.DDL:
                    if val in FORBIDDEN_KEYWORDS:
                        return False, f"Blocked keyword '{val}' detected in query."
                
                clean_val = val.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
                for forbidden in FORBIDDEN_KEYWORDS:
                    if forbidden in clean_val:
                        words = re.findall(r'\b[a-zA-Z_]+\b', val)
                        if forbidden in words:
                            return False, f"Blocked keyword '{forbidden}' detected in command."
        return True, "Query is safe."
                            
    safe, msg = check_tokens(stmt.tokens)
    if not safe:
        return False, msg
        
    return True, "Query is safe."

# Brute-force Login Protector (SEC-006)
class LoginProtector:
    def __init__(self):
        # Maps email/IP -> {count, lock_until}
        self.attempts: Dict[str, Dict[str, Any]] = {}
        
    def check_lock(self, email: str, ip: str) -> None:
        now = time.time()
        for key in [email, ip]:
            if key in self.attempts:
                record = self.attempts[key]
                if record["lock_until"] > now:
                    remaining = int(record["lock_until"] - now)
                    raise ValueError(f"Too many failed login attempts. Locked out. Please try again in {remaining} seconds.")
                    
    def record_success(self, email: str, ip: str) -> None:
        for key in [email, ip]:
            if key in self.attempts:
                self.attempts.pop(key)
                
    def record_failure(self, email: str, ip: str) -> int:
        now = time.time()
        max_attempts = 5
        lock_duration = 300  # 5 minutes
        
        for key in [email, ip]:
            if key not in self.attempts:
                self.attempts[key] = {"count": 0, "lock_until": 0.0}
            record = self.attempts[key]
            record["count"] += 1
            
            if record["count"] >= max_attempts:
                record["lock_until"] = now + lock_duration
                
        # Calculate exponential delay sleep
        count = max(self.attempts[email]["count"], self.attempts[ip]["count"])
        delay = min(1.5 ** count, 15.0)
        time.sleep(delay)
        return max_attempts - count

login_protector = LoginProtector()

# Database connection attempt protector for SQL connections (SEC-006)
class ConnectionAttemptProtector:
    def __init__(self):
        # Maps user_id -> {count, lock_until}
        self.attempts: Dict[str, Dict[str, Any]] = {}
        
    def check_lock(self, user_id: str) -> None:
        now = time.time()
        key = str(user_id)
        if key in self.attempts:
            record = self.attempts[key]
            if record["lock_until"] > now:
                remaining_seconds = int(record["lock_until"] - now)
                hours = remaining_seconds // 3600
                minutes = (remaining_seconds % 3600) // 60
                seconds = remaining_seconds % 60
                time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else (f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s")
                raise ValueError(f"Too many failed database connection attempts. Locked out. Please try again in {time_str}.")
                
    def record_success(self, user_id: str) -> None:
        key = str(user_id)
        if key in self.attempts:
            self.attempts.pop(key)
            
    def record_failure(self, user_id: str) -> int:
        now = time.time()
        key = str(user_id)
        max_attempts = 3
        lock_duration = 3 * 3600  # 3 hours
        
        if key not in self.attempts:
            self.attempts[key] = {"count": 0, "lock_until": 0.0}
        record = self.attempts[key]
        record["count"] += 1
        
        if record["count"] >= max_attempts:
            record["lock_until"] = now + lock_duration
            
        return max_attempts - record["count"]

connection_protector = ConnectionAttemptProtector()

# API Rate Limiter (SEC-007)
class RateLimiter:
    def __init__(self):
        # Maps user_id/ip + endpoint -> list of timestamps
        self.requests: Dict[str, List[float]] = {}
        
    def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        if key not in self.requests:
            self.requests[key] = []
            
        timestamps = self.requests[key]
        timestamps = [t for t in timestamps if now - t < window]
        self.requests[key] = timestamps
        
        if len(timestamps) >= limit:
            return True
            
        timestamps.append(now)
        return False

rate_limiter = RateLimiter()


# Workspace Concurrency Lock Manager (SEC-006)
class WorkspaceLockManager:
    def __init__(self):
        import asyncio
        from collections import defaultdict
        self._locks = defaultdict(asyncio.Lock)
        
    def get_lock(self, workspace_id):
        return self._locks[workspace_id]

workspace_lock_manager = WorkspaceLockManager()
