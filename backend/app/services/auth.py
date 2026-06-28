import hashlib
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from sqlalchemy import select
from app.models.models import User, UserSession
from app.repositories.repositories import UserRepository
from app.schemas.schemas import UserRegister, UserLogin
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_access_token
from app.core.logging import logger

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def register_user(self, user_in: UserRegister) -> Optional[User]:
        logger.info(f"Registering user with email: {user_in.email}")
        existing = await self.repo.get_by_email(user_in.email)
        if existing:
            logger.warning(f"Registration failed: user {user_in.email} already exists.")
            return None
            
        hashed = hash_password(user_in.password)
        db_user = User(
            email=user_in.email,
            password_hash=hashed
        )
        created = await self.repo.create(db_user)
        logger.info(f"User {created.id} successfully registered.")
        return created

    async def authenticate_user(self, login_in: UserLogin) -> Optional[User]:
        logger.info(f"Authenticating user: {login_in.email}")
        user = await self.repo.get_by_email(login_in.email)
        if not user:
            logger.warning(f"Authentication failed: user {login_in.email} not found.")
            return None
            
        if not verify_password(login_in.password, user.password_hash):
            logger.warning(f"Authentication failed: password mismatch for user {login_in.email}.")
            return None
            
        logger.info(f"User {user.email} authenticated successfully.")
        return user

    async def create_session(
        self, user: User, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> Tuple[str, str, UserSession]:
        session_id = uuid.uuid4()
        user_data = {"sub": user.email, "user_id": str(user.id)}
        
        access_token = create_access_token(data=user_data, jti=str(session_id))
        refresh_token = create_refresh_token(data=user_data, jti=str(session_id))
        
        rt_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        session = UserSession(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=rt_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=expires_at
        )
        self.db.add(session)
        await self.db.flush()
        logger.info(f"Created session {session_id} for user {user.email}")
        return access_token, refresh_token, session

    async def refresh_session(
        self, refresh_token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> Tuple[str, str]:
        payload = decode_access_token(refresh_token)
        if not payload:
            raise ValueError("Invalid refresh token.")
            
        session_id_str = payload.get("jti")
        user_id_str = payload.get("user_id")
        email = payload.get("sub")
        if not session_id_str or not user_id_str or not email:
            raise ValueError("Malformed refresh token claims.")
            
        session_id = uuid.UUID(session_id_str)
        user_id = uuid.UUID(user_id_str)
        
        # Check database session status
        q = await self.db.execute(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        )
        session = q.scalar_one_or_none()
        if not session:
            raise ValueError("Session is inactive or expired.")
            
        # Verify hash
        rt_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        if session.refresh_token_hash != rt_hash:
            # Token reuse/replay detected! Revoke all sessions for the user to be safe
            logger.error(f"Replay attack detected for session {session_id}! Revoking all sessions for user {user_id}.")
            await self.logout_all_sessions(user_id)
            await self.db.commit()
            raise ValueError("Token validation failed. Replay detected.")
            
        # Rotate refresh token
        user_data = {"sub": email, "user_id": str(user_id)}
        new_access_token = create_access_token(data=user_data, jti=str(session_id))
        new_refresh_token = create_refresh_token(data=user_data, jti=str(session_id))
        
        new_hash = hashlib.sha256(new_refresh_token.encode("utf-8")).hexdigest()
        session.refresh_token_hash = new_hash
        session.expires_at = datetime.utcnow() + timedelta(days=7)
        if ip_address:
            session.ip_address = ip_address
        if user_agent:
            session.user_agent = user_agent
            
        self.db.add(session)
        await self.db.flush()
        logger.info(f"Rotated tokens for session {session_id}")
        return new_access_token, new_refresh_token

    async def logout_session(self, refresh_token: str) -> None:
        payload = decode_access_token(refresh_token)
        if not payload:
            return
        session_id_str = payload.get("jti")
        if not session_id_str:
            return
        session_id = uuid.UUID(session_id_str)
        q = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        session = q.scalar_one_or_none()
        if session:
            session.is_active = False
            self.db.add(session)
            await self.db.flush()
            logger.info(f"Logged out session {session_id}")

    async def get_active_sessions(self, user_id: uuid.UUID) -> List[UserSession]:
        q = await self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).order_by(UserSession.created_at.desc())
        )
        return list(q.scalars().all())

    async def revoke_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
        q = await self.db.execute(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id
            )
        )
        session = q.scalar_one_or_none()
        if session:
            session.is_active = False
            self.db.add(session)
            await self.db.flush()
            logger.info(f"Revoked session {session_id} for user {user_id}")
            return True
        return False

    async def logout_all_sessions(self, user_id: uuid.UUID) -> None:
        q = await self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        )
        sessions = q.scalars().all()
        for session in sessions:
            session.is_active = False
            self.db.add(session)
        await self.db.flush()
        logger.info(f"Revoked all sessions for user {user_id}")

    def create_token_for_user(self, user: User) -> str:
        return create_access_token(data={"sub": user.email, "user_id": str(user.id)})
