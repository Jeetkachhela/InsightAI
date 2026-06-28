import pytest
from datetime import timedelta
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token, encrypt_credential, decrypt_credential

def test_password_hashing():
    pwd = "supersecretpassword123"
    hashed = hash_password(pwd)
    
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_jwt_tokens():
    data = {"sub": "test@user.com", "user_id": "8f51a2d1-d36d-4fbb-9a8c-b3bfef7b4e9f"}
    token = create_access_token(data, expires_delta=timedelta(minutes=10))
    
    assert isinstance(token, str)
    
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "test@user.com"
    assert decoded["user_id"] == "8f51a2d1-d36d-4fbb-9a8c-b3bfef7b4e9f"

def test_aes_credential_encryption():
    secret_conn_str = "postgresql://myuser:mypassword@localhost:5432/mydb"
    encrypted = encrypt_credential(secret_conn_str)
    
    assert encrypted != secret_conn_str
    
    decrypted = decrypt_credential(encrypted)
    assert decrypted == secret_conn_str
