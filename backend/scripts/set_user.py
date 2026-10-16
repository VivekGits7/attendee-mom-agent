import argparse
import asyncio
import getpass

from pydantic import ValidationError

from app.auth.model import User
from app.auth.schemas import SignupRequest
from app.auth.service import register_user
from app.auth.utils import hash_password
from app.database import close_db_pool, create_db_pool
from app.error import AppException


def read_password(password: str | None) -> str:
    if password:
        return password
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    return password


async def set_user(data: SignupRequest) -> str:
    await create_db_pool()
    try:
        user = await User.find_by_email(data.email)
        if user is None:
            await register_user(data)
            return f"Created {data.email}, it can log in now"
        await user.update_password(hash_password(data.password))
        return f"Password updated for {user.email}, its old sessions are logged out"
    finally:
        await close_db_pool()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Meeting Console login, or reset its password if it exists")
    parser.add_argument("email", help="Work email on an allowed signup domain")
    parser.add_argument("--name", help="Display name for a new user, defaults to the part before the @")
    parser.add_argument("--password", help="Skips the prompt, but the password lands in shell history")
    args = parser.parse_args()

    try:
        data = SignupRequest(
            full_name=args.name or args.email.split("@")[0],
            email=args.email,
            password=read_password(args.password),
        )
    except ValidationError as e:
        raise SystemExit("\n".join(f"{err['loc'][0]}: {err['msg']}" for err in e.errors()))

    try:
        print(asyncio.run(set_user(data)))
    except AppException as e:
        raise SystemExit(e.detail)


if __name__ == "__main__":
    main()
