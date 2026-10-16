import uuid
from datetime import datetime
from typing import Optional

from app.database import execute_command, execute_command_with_return, execute_query_one


class User:
    def __init__(self, **kwargs):
        self.user_id = kwargs.get("user_id")
        self.full_name = kwargs.get("full_name")
        self.email = kwargs.get("email")
        self.password_hash = kwargs.get("password_hash")
        self.token_version = kwargs.get("token_version", 0)
        self.last_login_at = kwargs.get("last_login_at")
        self.password_changed_at = kwargs.get("password_changed_at")
        self.created_at = kwargs.get("created_at")
        self.updated_at = kwargs.get("updated_at")

    @classmethod
    async def find_by_id(cls, user_id: str) -> Optional["User"]:
        row = await execute_query_one("SELECT * FROM users WHERE user_id = $1", uuid.UUID(user_id))
        return cls(**dict(row)) if row else None

    @classmethod
    async def find_by_email(cls, email: str) -> Optional["User"]:
        row = await execute_query_one("SELECT * FROM users WHERE LOWER(email) = LOWER($1)", email)
        return cls(**dict(row)) if row else None

    @classmethod
    async def create(cls, full_name: str, email: str, password_hash: str) -> Optional["User"]:
        # A parallel signup with the same email returns None instead of a 500.
        row = await execute_command_with_return(
            # SQL
            """
            INSERT INTO users (user_id, full_name, email, password_hash, last_login_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT DO NOTHING
            RETURNING *
            """,
            uuid.uuid4(),
            full_name,
            email,
            password_hash,
        )
        return cls(**dict(row)) if row else None

    async def mark_login(self) -> None:
        row = await execute_command_with_return(
            "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE user_id = $1 RETURNING last_login_at, updated_at",
            self.user_id,
        )
        self.last_login_at, self.updated_at = row["last_login_at"], row["updated_at"]

    async def update_password(self, password_hash: str) -> None:
        row = await execute_command_with_return(
            # SQL
            """
            UPDATE users
            SET password_hash = $2, token_version = token_version + 1,
                password_changed_at = NOW(), updated_at = NOW()
            WHERE user_id = $1
            RETURNING token_version, password_changed_at, updated_at
            """,
            self.user_id,
            password_hash,
        )
        self.password_hash = password_hash
        self.token_version = row["token_version"]
        self.password_changed_at, self.updated_at = row["password_changed_at"], row["updated_at"]

    def to_dict(self) -> dict:
        return {
            "user_id": str(self.user_id),
            "full_name": self.full_name,
            "email": self.email,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "password_changed_at": self.password_changed_at.isoformat() if self.password_changed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_public_dict(self) -> dict:
        data = self.to_dict()
        data.pop("password_changed_at")
        data.pop("updated_at")
        return data


class RevokedToken:
    @classmethod
    async def add(cls, jti: str, user_id: uuid.UUID, expires_at: datetime) -> None:
        await execute_command(
            # SQL
            """
            INSERT INTO revoked_tokens (revoked_token_id, jti, user_id, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (jti) DO NOTHING
            """,
            uuid.uuid4(),
            jti,
            user_id,
            expires_at,
        )

    @classmethod
    async def is_revoked(cls, jti: str) -> bool:
        row = await execute_query_one("SELECT 1 FROM revoked_tokens WHERE jti = $1", jti)
        return row is not None

    @classmethod
    async def delete_expired(cls) -> None:
        await execute_command("DELETE FROM revoked_tokens WHERE expires_at < NOW()")
