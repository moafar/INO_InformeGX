"""Application configuration and environment resolution helpers."""

from __future__ import annotations

import os


LOCAL_APP_DATABASE_URL = "dbname=ergo_app user=rom"
LOCAL_CLINICAL_DATABASE_URL = "dbname=obsino user=rom"
LOCAL_SECRET_KEY = "dev-secret-key"


class BaseConfig:
    """Common settings for all environments."""

    ENVIRONMENT = "base"
    TESTING = False
    DEBUG = False


class DevelopmentConfig(BaseConfig):
    """Local development settings."""

    ENVIRONMENT = "development"
    DEBUG = True


class TestingConfig(BaseConfig):
    """Test settings."""

    ENVIRONMENT = "testing"
    TESTING = True


class ProductionConfig(BaseConfig):
    """Production settings."""

    ENVIRONMENT = "production"


CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    """Parse a boolean-like environment value."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_environment_name(explicit_name: str | None = None) -> str:
    """Return the requested environment name."""
    if explicit_name:
        return explicit_name.lower()
    return os.getenv("APP_ENV", "development").lower()


def get_config_class(explicit_name: str | None = None) -> type[BaseConfig]:
    """Resolve the configuration class for the selected environment."""
    environment_name = get_environment_name(explicit_name)
    try:
        return CONFIGS[environment_name]
    except KeyError as error:
        raise ValueError(f"Unsupported environment: {environment_name}") from error


def _resolve_database_url(
    environment_name: str,
    explicit_url: str | None,
    local_fallback: str,
    setting_name: str,
) -> str | None:
    if explicit_url:
        return explicit_url
    if environment_name == "development":
        return local_fallback
    if environment_name == "testing":
        return None
    raise RuntimeError(f"{setting_name} is required in production")


def resolve_app_database_url(
    environment_name: str,
    explicit_url: str | None,
) -> str | None:
    """Resolve the application read/write database URL."""
    return _resolve_database_url(
        environment_name,
        explicit_url,
        LOCAL_APP_DATABASE_URL,
        "APP_DATABASE_URL",
    )


def resolve_clinical_database_url(
    environment_name: str,
    explicit_url: str | None,
) -> str | None:
    """Resolve the read-only clinical database URL."""
    return _resolve_database_url(
        environment_name,
        explicit_url,
        LOCAL_CLINICAL_DATABASE_URL,
        "CLINICAL_DATABASE_URL",
    )


def resolve_secret_key(environment_name: str, explicit_value: str | None) -> str:
    """Resolve the Flask secret key."""
    if explicit_value:
        return explicit_value
    if environment_name in {"development", "testing"}:
        return LOCAL_SECRET_KEY
    raise RuntimeError("SECRET_KEY is required in production")


def resolve_cookie_secure(
    environment_name: str,
    explicit_value: str | bool | None,
) -> bool:
    """Resolve whether secure cookies are enabled."""
    if explicit_value is not None:
        return parse_bool(explicit_value)
    return environment_name == "production"
