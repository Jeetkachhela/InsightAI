import pytest
import time
import logging
from pydantic import ValidationError
from app.core.security import LoginProtector, RateLimiter
from app.core.logging import StructuredFormatter
from app.schemas.schemas import QueryRequest, SQLExecuteRequest, UserRegister

def test_login_protector_lockout():
    protector = LoginProtector()
    email = "target@user.com"
    ip = "192.168.1.50"
    
    # 4 failed attempts should not lock out yet
    for _ in range(4):
        protector.record_failure(email, ip)
        
    protector.check_lock(email, ip)  # Should not raise exception
    
    # 5th attempt triggers lockout
    protector.record_failure(email, ip)
    
    with pytest.raises(ValueError) as exc_info:
        protector.check_lock(email, ip)
    assert "locked out" in str(exc_info.value).lower()
    
    # Successful login resets attempts
    protector.record_success(email, ip)
    protector.check_lock(email, ip)  # Should succeed without exception now

def test_rate_limiter():
    limiter = RateLimiter()
    key = "user_123_route"
    
    # Allow 3 requests in a 10s window
    assert limiter.is_rate_limited(key, limit=3, window=10) is False  # 1st request
    assert limiter.is_rate_limited(key, limit=3, window=10) is False  # 2nd request
    assert limiter.is_rate_limited(key, limit=3, window=10) is False  # 3rd request
    assert limiter.is_rate_limited(key, limit=3, window=10) is True   # 4th request (rate limited)

def test_log_redaction_api_keys():
    formatter = StructuredFormatter()
    fake_gsk = "gsk_" + "RDADcUdtCI4bpGPg2ojSWGdyb3FYYKDWIV1JhTdwUgi3Vv0SdOHv"
    fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    logger_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg=f"API keys: {fake_gsk} and {fake_jwt}",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(logger_record)
    assert "[REDACTED_API_KEY]" in formatted
    assert "[REDACTED_JWT_TOKEN]" in formatted

def test_log_redaction_db_connection():
    formatter = StructuredFormatter()
    logger_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=12,
        msg="Database url: postgresql://neondb_owner:npg_Bg7dk1FCUtOz@ep-square-firefly-ats27s1s-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(logger_record)
    assert "[REDACTED_PASSWORD]" in formatted
    assert "Bg7dk1FCUtOz" not in formatted

def test_log_redaction_password_json():
    formatter = StructuredFormatter()
    logger_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=15,
        msg='Payload contains {"password": "supersecretpassword123"} or secret="mysecret"',
        args=(),
        exc_info=None
    )
    formatted = formatter.format(logger_record)
    assert "[REDACTED]" in formatted
    assert "supersecretpassword123" not in formatted

def test_request_bounds_validation():
    # Test message content (nl_query) maximum length of 4000
    with pytest.raises(ValidationError):
        QueryRequest(nl_query="a" * 4001, data_source_id="5c96a79c-c284-45f0-bf75-958db1f5fded")
        
    # Test valid message content
    req = QueryRequest(nl_query="a" * 4000, data_source_id="5c96a79c-c284-45f0-bf75-958db1f5fded")
    assert len(req.nl_query) == 4000

    # Test SQL action sql maximum length of 8000
    with pytest.raises(ValidationError):
        SQLExecuteRequest(sql="s" * 8001, data_source_id="5c96a79c-c284-45f0-bf75-958db1f5fded")
        
    req_sql = SQLExecuteRequest(sql="s" * 8000, data_source_id="5c96a79c-c284-45f0-bf75-958db1f5fded")
    assert len(req_sql.sql) == 8000
