from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from uuid import UUID
from typing import Optional
from app.core.config import settings
from app.core.database import get_db
from app.models.models import User
from app.repositories.repositories import UserRepository
from app.core.logging import logger
from app.core.security import rate_limiter

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 1. Check cookies first (SEC-005)
    token = request.cookies.get("access_token")
    
    # 2. Check Auth header as fallback for tests/external API clients
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise credentials_exception
        
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM],
            audience="insightforge-app",
            issuer="insightforge-auth"
        )
        if payload.get("iss") != "insightforge-auth" or payload.get("aud") != "insightforge-app":
            raise credentials_exception
            
        user_id_str: str = payload.get("user_id")
        jti_str: str = payload.get("jti")
        if user_id_str is None or jti_str is None:
            raise credentials_exception
        user_id = UUID(user_id_str)
        jti = UUID(jti_str)
    except (JWTError, ValueError) as e:
        logger.warning(f"Failed to authenticate user via token: {e}")
        raise credentials_exception
        
    # Immediate session revocation check (SEC-010)
    from app.models.models import UserSession
    from sqlalchemy import select
    from datetime import datetime, timezone
    
    session_check = await db.execute(
        select(UserSession).where(
            UserSession.id == jti,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
        )
    )
    db_session = session_check.scalar_one_or_none()
    if db_session is None:
        logger.warning(f"Session {jti} has been revoked or expired.")
        raise credentials_exception
        
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

# User-based Rate Limiter Dependency (SEC-007)
def check_rate_limit(limit: int, window: int = 60):
    async def dependency(request: Request, current_user: User = Depends(get_current_user)):
        key = f"user:{current_user.id}:{request.url.path}"
        if rate_limiter.is_rate_limited(key, limit, window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
    return dependency

# IP-based Rate Limiter Dependency for Public Endpoints (SEC-007)
def check_ip_rate_limit(limit: int, window: int = 60):
    async def dependency(request: Request):
        client_host = request.client.host if request.client else "unknown"
        key = f"ip:{client_host}:{request.url.path}"
        if rate_limiter.is_rate_limited(key, limit, window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
    return dependency


from app.core.security import CredentialEncryptor
import json

def get_encryptor() -> CredentialEncryptor:
    try:
        keys_map = json.loads(settings.AES_KEYS)
    except Exception:
        keys_map = {"v1": settings.AES_KEY}
    return CredentialEncryptor(keys_map, settings.ACTIVE_AES_KEY_VERSION)
