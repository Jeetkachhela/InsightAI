import pytest
import uuid
import json
import asyncio
from datetime import datetime, timedelta
from app.core.security import (
    create_access_token, create_refresh_token, decode_access_token,
    CredentialEncryptor, workspace_lock_manager
)

def test_xxhash_pure_python_fallback():
    import xxhash
    # Test that we can use xxh3_128 and xxh3_128_hexdigest without DLL errors
    h = xxhash.xxh3_128(b"hello")
    assert len(h.digest()) == 16
    assert len(h.hexdigest()) == 32
    assert xxhash.xxh3_128_hexdigest(b"hello") == h.hexdigest()
    assert len(xxhash.xxh64_hexdigest(b"hello")) == 16

def test_aes_key_rotation_and_fallback():
    keys = {
        "v1": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "v2": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    }
    encryptor = CredentialEncryptor(keys, "v2")
    
    plain = "database_password_123"
    # Encrypt under active version v2
    enc = encryptor.encrypt(plain)
    assert enc.startswith("v2:")
    
    # Decrypt version v2
    dec = encryptor.decrypt(enc)
    assert dec == plain
    
    # Decrypt version v1 (legacy simulation)
    legacy_encryptor = CredentialEncryptor({"v1": keys["v1"]}, "v1")
    legacy_enc = legacy_encryptor.encrypt(plain) # will start with "v1:"
    dec_fallback = encryptor.decrypt(legacy_enc)
    assert dec_fallback == plain
    
    # Decrypt raw base64 without prefix
    raw_b64 = legacy_enc.split(":", 1)[1]
    dec_raw = encryptor.decrypt(raw_b64)
    assert dec_raw == plain

def test_workspace_concurrency_locking():
    async def run_test():
        ws_id = uuid.uuid4()
        lock = workspace_lock_manager.get_lock(ws_id)
        
        assert lock.locked() is False
        async with lock:
            assert lock.locked() is True
            # Try to check locking state again
            assert workspace_lock_manager.get_lock(ws_id).locked() is True
            
        assert lock.locked() is False
    asyncio.run(run_test())
