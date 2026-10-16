from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import get_current_user, get_token_payload
from app.auth.model import User
from app.auth.schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginResponse,
    LogoutResponse,
    SignupRequest,
    SignupResponse,
    TokenPayload,
)
from app.auth.service import (
    authenticate_user,
    change_password,
    logout_user,
    register_user,
)
from app.auth.utils import access_token_expires_in
from app.common import (
    COMMON_ERROR_RESPONSES,
    BadRequestResponse,
    ConflictResponse,
    UnauthorizedResponse,
)
from app.error import AppException
from app.limiter import limiter
from app.logger import get_logger

logger = get_logger(__name__)

auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])


@auth_router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user account",
    responses={
        **COMMON_ERROR_RESPONSES,
        201: {"model": SignupResponse, "description": "Account created and logged in"},
        400: {
            "model": BadRequestResponse,
            "description": "Email is not on an allowed domain",
        },
        409: {"model": ConflictResponse, "description": "Email already registered"},
    },
)
@limiter.limit("10/minute")
async def signup(request: Request, data: SignupRequest) -> SignupResponse:
    """
    Create a user account and log the user in.

    - **full_name**: required, 2 to 255 chars
    - **email**: required, must be a tcgdigital.com address
    - **password**: required, 8 to 72 chars
    - returns an access token, send it as Authorization Bearer on protected endpoints
    """
    try:
        access_token, user = await register_user(data)
        return SignupResponse(
            success=True,
            message="Account created successfully",
            access_token=access_token,
            expires_in=access_token_expires_in(),
            data=user,
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in with email and password",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": LoginResponse, "description": "Login successful"},
        401: {
            "model": UnauthorizedResponse,
            "description": "Invalid email or password",
        },
    },
)
@limiter.limit("10/minute")
async def login(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends()
) -> LoginResponse:
    """
    Log in and get an access token.

    - **username**: required, the account email, sent as form data
    - **password**: required, sent as form data
    - works with the Swagger Authorize button
    """
    try:
        access_token, user = await authenticate_user(
            form_data.username, form_data.password
        )
        return LoginResponse(
            success=True,
            message="Login successful",
            access_token=access_token,
            expires_in=access_token_expires_in(),
            data=user,
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out the current session",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": LogoutResponse, "description": "Token revoked"},
        401: {
            "model": UnauthorizedResponse,
            "description": "Missing, invalid, or already revoked token",
        },
    },
)
@limiter.limit("30/minute")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    payload: TokenPayload = Depends(get_token_payload),
) -> LogoutResponse:
    """
    Log out by revoking the current access token.

    - header **Authorization**: Bearer token is required
    - only this token stops working, other logged in devices stay logged in
    - the frontend should also drop the stored token
    """
    try:
        await logout_user(current_user, payload)
        return LogoutResponse(success=True, message="Logged out successfully")
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change the account password",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": ChangePasswordResponse, "description": "Password updated"},
        400: {
            "model": BadRequestResponse,
            "description": "Wrong current password, new passwords do not match, or new password is the same",
        },
    },
)
@limiter.limit("10/minute")
async def change_password_endpoint(
    request: Request,
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
) -> ChangePasswordResponse:
    """
    Change the password of the logged in user.

    - **old_password**: required, the current password
    - **new_password**: required, 8 to 72 chars, must differ from the current one
    - **confirm_new_password**: required, must match new_password
    - header **Authorization**: Bearer token is required
    - logs out every other session, the frontend must store the new access token from this response
    """
    try:
        access_token = await change_password(current_user, data)
        return ChangePasswordResponse(
            success=True,
            message="Password updated successfully",
            access_token=access_token,
            expires_in=access_token_expires_in(),
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
