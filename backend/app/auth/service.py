from datetime import datetime, timezone

from app.auth.model import RevokedToken, User
from app.auth.schemas import (
    ChangePasswordRequest,
    SignupRequest,
    TokenPayload,
    UserData,
)
from app.auth.utils import create_access_token, hash_password, verify_password
from app.config import settings
from app.error import BadRequestException, ConflictException, UnauthorizedException

EMAIL_TAKEN_MESSAGE = "An account with this email already exists. Please log in."


def is_allowed_signup_email(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in settings.SIGNUP_EMAIL_DOMAINS


async def register_user(data: SignupRequest) -> tuple[str, UserData]:
    if not is_allowed_signup_email(data.email):
        domains = " or ".join(settings.SIGNUP_EMAIL_DOMAINS)
        raise BadRequestException(f"Please sign up with your {domains} email address")
    if await User.find_by_email(data.email):
        raise ConflictException(EMAIL_TAKEN_MESSAGE)
    user = await User.create(data.full_name, data.email, hash_password(data.password))
    if user is None:
        raise ConflictException(EMAIL_TAKEN_MESSAGE)
    return create_access_token(user.email, user.token_version), UserData(
        **user.to_public_dict()
    )


async def authenticate_user(email: str, password: str) -> tuple[str, UserData]:
    user = await User.find_by_email(email.strip())
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedException("Invalid email or password")
    await user.mark_login()
    return create_access_token(user.email, user.token_version), UserData(
        **user.to_public_dict()
    )


async def logout_user(user: User, payload: TokenPayload) -> None:
    await RevokedToken.add(
        payload.jti, user.user_id, datetime.fromtimestamp(payload.exp, tz=timezone.utc)
    )
    await RevokedToken.delete_expired()


async def change_password(user: User, data: ChangePasswordRequest) -> str:
    if data.new_password != data.confirm_new_password:
        raise BadRequestException("New password and confirm password do not match")
    if not verify_password(data.old_password, user.password_hash):
        raise BadRequestException("Current password is incorrect")
    if data.new_password == data.old_password:
        raise BadRequestException(
            "New password must be different from the current password"
        )
    await user.update_password(hash_password(data.new_password))
    return create_access_token(user.email, user.token_version)
