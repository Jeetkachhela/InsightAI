from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.schemas import UserRegister, UserLogin, Token, UserResponse, UserSessionResponse
from app.services.auth import AuthService
from app.api.deps import check_ip_rate_limit, get_current_user
from app.models.models import User, AuditLog
from app.repositories.repositories import AuditLogRepository
from app.core.security import login_protector
from app.core.config import settings
from typing import List
from uuid import UUID

router = APIRouter()

@router.post(
    "/register", 
    response_model=Token, 
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_ip_rate_limit(limit=5, window=60))]
)
async def register(
    user_in: UserRegister, 
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    auth_service = AuthService(db)
    user = await auth_service.register_user(user_in)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
    
    # Audit log (ARCH-002)
    audit_repo = AuditLogRepository(db)
    audit = AuditLog(
        user_id=user.id,
        action="USER_REGISTRATION",
        details=f"User registered with email: {user.email}",
        ip_address=ip
    )
    await audit_repo.log(audit)
    
    # Create active session and both tokens (SEC-005, SEC-009)
    access_token, refresh_token, session = await auth_service.create_session(
        user, ip_address=ip, user_agent=user_agent
    )
    
    # Set httponly secure cookies (SEC-005)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/"
    )
    
    # Audit log successful registration login
    await audit_repo.log(AuditLog(
        user_id=user.id,
        action="LOGIN_SUCCESS",
        details=f"User logged in automatically after registration: {user.email}. Session: {session.id}",
        ip_address=ip
    ))
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post(
    "/login", 
    response_model=Token,
    dependencies=[Depends(check_ip_rate_limit(limit=5, window=60))]
)
async def login(
    login_in: UserLogin, 
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # 1. Check if account/IP is locked (SEC-006)
    try:
        login_protector.check_lock(login_in.email, ip)
    except ValueError as e:
        # Audit log lockout (ARCH-002)
        audit_repo = AuditLogRepository(db)
        await audit_repo.log(AuditLog(
            action="LOGIN_LOCKOUT_BLOCKED",
            details=f"Locked out login attempt for email: {login_in.email}",
            ip_address=ip
        ))
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed login attempts. Please try again later."
        )
        
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(login_in)
    
    if not user:
        # 2. Record failure and trigger exponential delay (SEC-006)
        remaining = login_protector.record_failure(login_in.email, ip)
        
        audit_repo = AuditLogRepository(db)
        await audit_repo.log(AuditLog(
            action="LOGIN_FAILED",
            details=f"Failed login attempt for email: {login_in.email}",
            ip_address=ip
        ))
        
        detail_msg = "Incorrect email or password."
        if remaining <= 2:
            detail_msg += f" {remaining} attempts remaining before account lock."
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_msg
        )
        
    # 3. Successful login: clear protector tracking
    login_protector.record_success(login_in.email, ip)
    
    # Create active session and both tokens (SEC-005, SEC-009)
    access_token, refresh_token, session = await auth_service.create_session(
        user, ip_address=ip, user_agent=user_agent
    )
    
    # Set httponly secure cookies (SEC-005)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/"
    )
    
    # Audit log successful login (ARCH-002)
    audit_repo = AuditLogRepository(db)
    await audit_repo.log(AuditLog(
        user_id=user.id,
        action="LOGIN_SUCCESS",
        details=f"User logged in successfully: {user.email}. Session: {session.id}",
        ip_address=ip
    ))
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Check cookies first
    refresh_token = request.cookies.get("refresh_token")
    
    # Fallback to Authorization header if cookies not present (for external clients)
    if not refresh_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            refresh_token = auth_header.split(" ")[1]
            
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing."
        )
        
    auth_service = AuthService(db)
    try:
        new_access, new_refresh = await auth_service.refresh_session(
            refresh_token, ip_address=ip, user_agent=user_agent
        )
    except ValueError as e:
        # Clear cookies on failed refresh with exact matching attributes (SEC-005)
        response.delete_cookie(key="access_token", path="/", secure=not settings.DEBUG, samesite="lax", httponly=True)
        response.delete_cookie(key="refresh_token", path="/", secure=not settings.DEBUG, samesite="lax", httponly=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again."
        )
        
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/"
    )
    
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        auth_service = AuthService(db)
        await auth_service.logout_session(refresh_token)
        
    # Clear cookies with exact matching attributes (SEC-005)
    response.delete_cookie(key="access_token", path="/", secure=not settings.DEBUG, samesite="lax", httponly=True)
    response.delete_cookie(key="refresh_token", path="/", secure=not settings.DEBUG, samesite="lax", httponly=True)
    return {"detail": "Logged out successfully"}

@router.get("/sessions", response_model=List[UserSessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    return await auth_service.get_active_sessions(current_user.id)

@router.delete("/sessions/logout-all")
async def logout_all_devices(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    await auth_service.logout_all_sessions(current_user.id)
    
    # Clear cookies with exact matching attributes (SEC-005)
    response.delete_cookie(key="access_token", path="/", secure=not settings.DEBUG, samesite="lax", httponly=True)
    response.delete_cookie(key="refresh_token", path="/", secure=not settings.DEBUG, samesite="lax", httponly=True)
    return {"detail": "Logged out from all devices"}

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    success = await auth_service.revoke_session(current_user.id, session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked."
        )
    return {"detail": "Session revoked successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    # Session check (FE-010)
    return current_user
