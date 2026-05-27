"""
Authentication Endpoints for SalonAI Workforce Platform.
Implements credentials validation, JWT issuance, token refresh, logout, and self profile query.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from db import get_db, User, UserRole
from core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)
from api.deps import get_current_user
import jwt

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Pydantic Schemas ---

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="owner@salonai.com")
    password: str = Field(..., example="password123")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole
    email: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserMeResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    is_active: bool
    staff_id: Optional[str] = None


# --- Endpoints ---

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticate user with email and password, returning access and refresh JWT tokens."
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate and issue JWT tokens."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or inactive"
        )
        
    # Generate tokens
    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id)
    
    # Store refresh token in database for session tracking & revocation
    user.refresh_token = refresh_token
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role,
        email=user.email
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Acquire a new access token using a valid, active refresh token."
)
def refresh_token(
    payload: RefreshRequest,
    db: Session = Depends(get_db)
):
    """Validate refresh token and issue new access token."""
    try:
        decoded = decode_token(payload.refresh_token)
        user_id_str = decoded.get("sub")
        token_type = decoded.get("type")
        
        if not user_id_str or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token structure",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token signature.",
        )
        
    import uuid
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
        )
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
        
    # Verify the token matches the stored token (revocation support)
    if user.refresh_token != payload.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked or replaced.",
        )
        
    # Issue fresh tokens (refresh token rotation)
    new_access_token = create_access_token(subject=user.id, role=user.role.value)
    new_refresh_token = create_refresh_token(subject=user.id)
    
    user.refresh_token = new_refresh_token
    db.commit()
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        role=user.role,
        email=user.email
    )


@router.post(
    "/logout",
    summary="Revoke Session (Logout)",
    description="Revoke the active refresh token and invalidate the user session."
)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log out user by revoking their stored refresh token."""
    current_user.refresh_token = None
    db.commit()
    return {"message": "Successfully logged out and session revoked."}


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Query Current User Profile",
    description="Retrieve the profile metadata of the currently logged-in user."
)
def me(current_user: User = Depends(get_current_user)):
    """Fetch profile info of authenticated user."""
    return UserMeResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        staff_id=str(current_user.staff_id) if current_user.staff_id else None
    )
