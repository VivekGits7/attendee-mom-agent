from urllib.parse import unquote, urlsplit

from app.config import Settings


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
