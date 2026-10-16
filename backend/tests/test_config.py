from urllib.parse import unquote, urlsplit

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("secret", ["change-me", "too-short"])
def test_production_rejects_weak_jwt_secret(secret):
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY=secret)


def test_production_accepts_long_jwt_secret():
    config = Settings(ENVIRONMENT="production", JWT_SECRET_KEY="x" * 48)
    assert config.is_production


def test_signup_domains_are_normalized():
    config = Settings(SIGNUP_EMAIL_DOMAINS=["@TCGDigital.com"])
    assert config.SIGNUP_EMAIL_DOMAINS == ["tcgdigital.com"]


def test_database_url_encodes_credentials_and_database_name():
    config = Settings(
        POSTGRES_DB_HOST="localhost",
        POSTGRES_DB_PORT=5432,
        POSTGRES_DB_USER="user@org",
        POSTGRES_DB_PASSWORD="pa@ss:/?#%",
        POSTGRES_DB_NAME="mom/db",
    )

    parsed = urlsplit(config.database_url)

    assert parsed.hostname == "localhost"
    assert parsed.port == 5432
    assert unquote(parsed.username) == "user@org"
    assert unquote(parsed.password) == "pa@ss:/?#%"
    assert unquote(parsed.path.lstrip("/")) == "mom/db"
