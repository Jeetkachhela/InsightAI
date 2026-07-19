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

def test_get_current_user_header_precedence():
    from unittest.mock import AsyncMock, MagicMock
    from uuid import uuid4
    from datetime import datetime, timezone, timedelta
    from app.api.deps import get_current_user
    from app.models.models import User, UserSession
    from app.core.security import create_access_token
    
    user_id = uuid4()
    session_id = uuid4()
    
    user_data = {"sub": "test@user.com", "user_id": str(user_id)}
    valid_header_token = create_access_token(data=user_data, jti=str(session_id))
    expired_cookie_token = "malformed_or_expired_jwt"
    
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {valid_header_token}"}
    request.cookies = {"access_token": expired_cookie_token}
    
    db = AsyncMock()
    
    mock_session = UserSession(
        id=session_id,
        user_id=user_id,
        is_active=True,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    )
    
    mock_user = User(
        id=user_id,
        email="test@user.com"
    )
    
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = mock_session
    
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user
    
    db.execute.side_effect = [session_result, user_result]
    
    async def run_get_user():
        return await get_current_user(request=request, db=db)
        
    current_user = asyncio.run(run_get_user())
    
    assert current_user.id == user_id
    assert current_user.email == "test@user.com"
    assert db.execute.call_count == 2

def test_metrics_endpoint_unauthenticated():
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    response = client.get("/api/v1/system/metrics")
    assert response.status_code == 401

def test_query_log_repository_deletion():
    from unittest.mock import AsyncMock, MagicMock
    from uuid import uuid4
    from app.repositories.repositories import QueryLogRepository
    from app.models.models import QueryLog
    
    db = AsyncMock()
    user_id = uuid4()
    log_id = uuid4()
    
    repo = QueryLogRepository(db)
    
    mock_log = QueryLog(id=log_id, user_id=user_id, query_text="SELECT 1")
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = mock_log
    db.execute.return_value = exec_res
    
    async def run_delete():
        return await repo.delete_by_id(log_id, user_id)
        
    res = asyncio.run(run_delete())
    assert res is True
    db.delete.assert_called_once_with(mock_log)


