"""
KeepSafe Backend — User Authentication API

Endpoints for user registration, login, and profile management.
Uses email + password authentication with JWT tokens.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import Base, Column, DateTime, String, Integer, Boolean, func, get_db
from app.db import User, UserDevice, Device, UserPushToken

logger = logging.getLogger("keepsafe.api.users")

router = APIRouter(prefix="/api/v1/users", tags=["users"])

# ── Password Hashing ───────────────────────────────────────────
# Use bcrypt via passlib (from requirements.txt: passlib[bcrypt])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed: str) -> bool:
    return pwd_context.verify(plain_password, hashed)


# ── JWT ────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Decode and validate a JWT token. Returns user_id on success."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Pydantic Schemas ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class UserProfileOut(BaseModel):
    user_id: str
    email: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


class DeviceOut(BaseModel):
    device_id: str
    nickname: Optional[str] = None
    bound_at: datetime
    is_active: bool
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class PushTokenRequest(BaseModel):
    platform: str  # "ios" or "android"
    token: str


# ── Dependencies ───────────────────────────────────────────────

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate JWT from Authorization header."""
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header required")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization scheme must be Bearer")

    user_id = decode_access_token(token)

    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# ── Endpoints ──────────────────────────────────────────────────

@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account with email and password.
    """
    # Check if email already exists
    stmt = select(User).where(User.email == req.email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Generate unique user_id
    import uuid
    user_id = str(uuid.uuid4())

    user = User(
        user_id=user_id,
        email=req.email,
        hashed_password=hash_password(req.password),
        nickname=req.nickname or req.email.split("@")[0],
    )
    db.add(user)
    await db.commit()

    logger.info("User registered: user_id=%s email=%s", user_id, req.email)
    return MessageResponse(message="User registered successfully")


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email + password. Returns a JWT access token.
    """
    stmt = select(User).where(User.email == req.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.user_id)

    logger.info("User logged in: user_id=%s", user.user_id)
    return LoginResponse(access_token=token, user_id=user.user_id)


@router.get("/profile", response_model=UserProfileOut)
async def get_profile(current_user: User = Depends(get_current_user)):
    """
    Get the current user's profile.
    """
    return UserProfileOut.model_validate(current_user)


@router.put("/profile", response_model=UserProfileOut)
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the current user's profile (nickname, avatar_url, phone).
    """
    if req.nickname is not None:
        current_user.nickname = req.nickname
    if req.avatar_url is not None:
        current_user.avatar_url = req.avatar_url
    if req.phone is not None:
        current_user.phone = req.phone

    await db.commit()
    await db.refresh(current_user)

    logger.info("User profile updated: user_id=%s", current_user.user_id)
    return UserProfileOut.model_validate(current_user)


@router.get("/me/devices", response_model=List[DeviceOut])
async def get_my_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all devices bound to the current user.
    """
    stmt = (
        select(UserDevice, Device)
        .join(Device, UserDevice.device_id == Device.device_id)
        .where(
            UserDevice.user_id == current_user.user_id,
            UserDevice.is_bound == True,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    devices = []
    for ud, d in rows:
        devices.append(
            DeviceOut(
                device_id=ud.device_id,
                nickname=ud.nickname,
                bound_at=ud.bound_at,
                is_active=d.is_active,
                last_seen=d.last_seen,
            )
        )
    return devices


@router.post("/me/push-token", response_model=MessageResponse)
async def register_push_token(
    req: PushTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a device push notification token (FCM/APNs).
    """
    if req.platform not in ("ios", "android"):
        raise HTTPException(status_code=400, detail="Platform must be 'ios' or 'android'")

    if not req.token or len(req.token.strip()) == 0:
        raise HTTPException(status_code=400, detail="Token is required")

    # Upsert: find existing token for this user + platform, or create new
    stmt = select(UserPushToken).where(
        UserPushToken.user_id == current_user.user_id,
        UserPushToken.platform == req.platform,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.token = req.token
        existing.updated_at = datetime.now(timezone.utc)
    else:
        push_token = UserPushToken(
            user_id=current_user.user_id,
            platform=req.platform,
            token=req.token,
        )
        db.add(push_token)

    await db.commit()

    logger.info(
        "Push token registered: user_id=%s platform=%s token=%s",
        current_user.user_id,
        req.platform,
        req.token[:16],
    )
    return MessageResponse(message="Push token registered successfully")
