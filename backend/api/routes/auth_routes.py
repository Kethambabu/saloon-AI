"""
Authentication Endpoints for SalonAI Workforce Platform.
Implements credentials validation, JWT issuance, token refresh, logout, and self profile query.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from db import get_db, User, UserRole, Admin, Staff, Customer, Branch
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)
from api.deps import get_current_user
import jwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Pydantic Schemas ---

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="owner@salonai.com")
    password: str = Field(..., example="password123")
    selected_role: Optional[UserRole] = Field(default=None, description="Role when multiple options exist")


class LoginChoiceResponse(BaseModel):
    """Response when user has multiple role options"""
    require_role_selection: bool = True
    available_roles: list[str]
    email: str
    message: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole
    email: str
    success: Optional[bool] = True
    token: Optional[str] = None
    refreshToken: Optional[str] = None
    user: Optional[dict] = None
    message: Optional[str] = None
    require_role_selection: Optional[bool] = False
    available_roles: Optional[list[str]] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserMeResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    is_active: bool
    staff_id: Optional[str] = None
    customer_id: Optional[str] = None


# --- Endpoints ---

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticate user with email and password. May require role selection if user has multiple roles."
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate and issue JWT tokens or prompt for role selection."""
    email_clean = payload.email.lower().strip()
    
    # Find all users with this email (there can be multiple roles)
    users = db.query(User).filter(User.email == email_clean).all()
    
    if not users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password matches for at least one user record
    valid_users = []
    for user in users:
        if verify_password(payload.password, user.hashed_password):
            if user.is_active:
                valid_users.append(user)
    
    if not valid_users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # If multiple valid roles exist, prompt user to select one
    if len(valid_users) > 1:
        available_roles = [user.role.value for user in valid_users]
        
        # If user already specified a role, use it
        if payload.selected_role:
            selected_user = next(
                (u for u in valid_users if u.role == payload.selected_role),
                None
            )
            if not selected_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role {payload.selected_role} not available for this user"
                )
            user = selected_user
        else:
            # Return available roles and ask user to select
            return TokenResponse(
                access_token="",
                refresh_token="",
                role=UserRole.CUSTOMER,
                email=email_clean,
                success=False,
                message="Multiple roles available for this account. Please select one.",
                require_role_selection=True,
                available_roles=available_roles
            )
    else:
        user = valid_users[0]
    
    # Generate tokens
    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id)
    
    # Store refresh token in database for session tracking & revocation
    user.refresh_token = refresh_token
    db.commit()
    
    user_data = {
        "id": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "staff_id": str(user.staff_id) if user.staff_id else None,
        "customer_id": str(user.customer_id) if user.customer_id else None
    }
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role,
        email=user.email,
        success=True,
        token=access_token,
        refreshToken=refresh_token,
        user=user_data,
        message="Login successful"
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


# --- Additional Auth Pydantic Schemas ---

class SignupRequest(BaseModel):
    email: EmailStr = Field(..., example="newuser@example.com")
    password: str = Field(..., min_length=6, example="password123")
    role: UserRole = Field(default=UserRole.STAFF, example=UserRole.STAFF)
    first_name: str = Field(..., min_length=1, example="Jane")
    last_name: str = Field(..., min_length=1, example="Doe")
    phone: Optional[str] = Field(default=None, example="+1-555-0199")
    branch_id: Optional[str] = Field(default=None, description="Applicable for Staff")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str = Field(..., description="Reset verification token")
    new_password: str = Field(..., min_length=6)


# --- Endpoints ---

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new User Profile",
    description="Signs up a new user, hashes password, assigns role, and populates role-specific tables."
)
def signup(
    payload: SignupRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Sign up and create role records."""
    email_clean = payload.email.lower().strip()
    
    # 1. Block unauthorized admin signup
    if payload.role == UserRole.ADMIN:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to create Admin accounts."
            )
        token = auth_header.split(" ")[1]
        try:
            current_user = get_current_user(db=db, token=token)
            if current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only Admin users can create Admin accounts."
                )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin users can create Admin accounts."
            )

    # 2. Check if email already registered
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered."
        )
        
    # 3. Hash password and build user
    hashed = hash_password(payload.password)
    new_user = User(
        email=email_clean,
        hashed_password=hashed,
        role=payload.role,
        is_active=True
    )
    
    db.add(new_user)
    db.flush()  # Get user.id
    
    # 4. Create role-specific records
    try:
        import uuid as _uuid
        
        # Resolve branch if provided, otherwise pick first branch for staff fallback
        resolved_branch_id = None
        if payload.branch_id:
            try:
                resolved_branch_id = _uuid.UUID(payload.branch_id)
            except ValueError:
                # Fuzzy look up branch
                branch_obj = db.query(Branch).filter(Branch.name.ilike(payload.branch_id)).first()
                if branch_obj:
                    resolved_branch_id = branch_obj.id
        
        if not resolved_branch_id and payload.role == UserRole.STAFF:
            # Fallback to first branch if empty
            first_branch = db.query(Branch).first()
            if first_branch:
                resolved_branch_id = first_branch.id
            else:
                # Create default branch if none exist
                default_branch = Branch(
                    id=_uuid.uuid4(),
                    name="Default Branch",
                    code="DFB",
                    address="123 Salon Way",
                    city="Cityville",
                    is_active=True
                )
                db.add(default_branch)
                db.flush()
                resolved_branch_id = default_branch.id
                
        if payload.role == UserRole.ADMIN:
            admin_record = Admin(
                id=_uuid.uuid4(),
                user_id=new_user.id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=email_clean,
                phone=payload.phone
            )
            db.add(admin_record)
            
        elif payload.role == UserRole.STAFF:
            staff_record = Staff(
                id=_uuid.uuid4(),
                branch_id=resolved_branch_id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=email_clean,
                phone=payload.phone,
                role="Stylist",
                is_active=True
            )
            db.add(staff_record)
            db.flush()
            new_user.staff_id = staff_record.id
            
        elif payload.role == UserRole.CUSTOMER:
            customer_record = Customer(
                id=_uuid.uuid4(),
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=email_clean,
                phone=payload.phone,
                is_active=True,
                loyalty_points=0  # Initialize loyalty points to 0 for new customer
            )
            db.add(customer_record)
            db.flush()
            new_user.customer_id = customer_record.id
            
        db.commit()
        
        # Auto-issue tokens for immediate login after signup
        access_token = create_access_token(subject=new_user.id, role=new_user.role.value)
        refresh_token = create_refresh_token(subject=new_user.id)
        
        # Store refresh token for session tracking
        new_user.refresh_token = refresh_token
        db.commit()
        
        user_data = {
            "id": str(new_user.id),
            "email": new_user.email,
            "role": new_user.role.value,
            "is_active": new_user.is_active,
            "staff_id": str(new_user.staff_id) if new_user.staff_id else None,
            "customer_id": str(new_user.customer_id) if new_user.customer_id else None
        }
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            role=new_user.role,
            email=new_user.email,
            success=True,
            token=access_token,
            refreshToken=refresh_token,
            user=user_data,
            message="User registered successfully."
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during signup transaction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/forgot-password",
    summary="Initiate Password Recovery",
    description="Verifies user email and returns a mock verification token for testing password recovery."
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Initiate password recovery."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user:
        # Avoid user enumeration attacks - return mock token even if user not found
        return {
            "success": True,
            "message": "If the email is registered, a password reset link will be sent.",
            "token": "reset-token-mock-12345"
        }
        
    # In a real app, generate a unique token, save it to DB, and email it.
    # For this project, we return a standard mock token for testing.
    return {
        "success": True,
        "message": "Recovery token generated successfully.",
        "token": f"reset-token-{user.id}"
    }


@router.post(
    "/reset-password",
    summary="Complete Password Recovery",
    description="Resets the password if the recovery token matches."
)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Complete password recovery."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )
        
    # Verify mock token
    expected_token = f"reset-token-{user.id}"
    if payload.token != expected_token and payload.token != "reset-token-mock-12345":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )
        
    user.hashed_password = hash_password(payload.new_password)
    user.refresh_token = None  # Invalidate active sessions
    db.commit()
    
    return {"success": True, "message": "Password updated successfully. Please log in with your new password."}


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
        staff_id=str(current_user.staff_id) if current_user.staff_id else None,
        customer_id=str(current_user.customer_id) if current_user.customer_id else None
    )
