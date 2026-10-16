from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.common import BaseResponse

USER_EXAMPLE = {
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "full_name": "TCG User",
    "email": "tcg@tcgdigital.com",
    "last_login_at": "2026-10-16T10:30:00+00:00",
    "created_at": "2026-10-16T10:30:00+00:00",
}

TOKEN_EXAMPLE = {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0Y2dAdGNnZGlnaXRhbC5jb20ifQ.sig",
    "token_type": "bearer",
    "expires_in": 86400,
}


class SignupRequest(BaseModel):
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="User display name",
        examples=["TCG User"],
    )
    email: EmailStr = Field(
        ...,
        description="Work email on an allowed domain",
        examples=["tcg@tcgdigital.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Account password, 8 to 72 characters",
        examples=["Str0ngPass!"],
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "TCG User",
                "email": "tcg@tcgdigital.com",
                "password": "Str0ngPass!",
            }
        }
    )


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(
        ...,
        min_length=1,
        max_length=72,
        description="Current account password",
        examples=["Str0ngPass!"],
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="New password, 8 to 72 characters",
        examples=["N3wStr0ngPass!"],
    )
    confirm_new_password: str = Field(
        ...,
        min_length=1,
        max_length=72,
        description="New password typed again, must match new_password",
        examples=["N3wStr0ngPass!"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "old_password": "Str0ngPass!",
                "new_password": "N3wStr0ngPass!",
                "confirm_new_password": "N3wStr0ngPass!",
            }
        }
    )


class TokenPayload(BaseModel):
    sub: str = Field(
        ..., description="Email of the token owner", examples=["tcg@tcgdigital.com"]
    )
    ver: int = Field(
        ..., description="User token version when the token was issued", examples=[0]
    )
    jti: str = Field(
        ...,
        description="Unique token id used to log out",
        examples=["kT3x9QeVw2Lr8sYb"],
    )
    exp: int = Field(
        ..., description="Expiry time as a unix timestamp", examples=[1792137600]
    )


class UserData(BaseModel):
    user_id: str = Field(
        ..., description="User UUID", examples=[USER_EXAMPLE["user_id"]]
    )
    full_name: str = Field(
        ..., description="User display name", examples=[USER_EXAMPLE["full_name"]]
    )
    email: str = Field(
        ..., description="User email address", examples=[USER_EXAMPLE["email"]]
    )
    last_login_at: Optional[str] = Field(
        None,
        description="ISO 8601 time of the last login",
        examples=[USER_EXAMPLE["last_login_at"]],
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 time the account was created",
        examples=[USER_EXAMPLE["created_at"]],
    )


class _TokenResponse(BaseResponse):
    access_token: str = Field(
        ...,
        description="JWT sent as a Bearer token",
        examples=[TOKEN_EXAMPLE["access_token"]],
    )
    token_type: str = Field(
        default="bearer", description="Token type", examples=["bearer"]
    )
    expires_in: int = Field(
        ..., description="Seconds until the token expires", examples=[86400]
    )


class SignupResponse(_TokenResponse):
    data: UserData = Field(..., description="Created user")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Account created successfully",
                **TOKEN_EXAMPLE,
                "data": USER_EXAMPLE,
            }
        }
    )


class LoginResponse(_TokenResponse):
    data: UserData = Field(..., description="Logged in user")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Login successful",
                **TOKEN_EXAMPLE,
                "data": USER_EXAMPLE,
            }
        }
    )


class ChangePasswordResponse(_TokenResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password updated successfully",
                **TOKEN_EXAMPLE,
            }
        }
    )


class LogoutResponse(BaseResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"success": True, "message": "Logged out successfully"}
        }
    )
