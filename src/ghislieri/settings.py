"""Runtime configuration, read from GS_* environment variables and an optional .env file."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Telegram id of the production bot (the number before ":" in its token). Not a secret.
PROD_BOT_ID = 2137673445
# Present only on the production server (mounted read-only into the container).
PROD_MARKER = Path("/etc/ghislieri/production")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GS_", env_file=".env", extra="ignore")

    env: Literal["dev", "prod"] = "dev"
    bot_token: SecretStr
    data_dir: Path = Path("var")
    log_level: str = "INFO"
    # Chat that receives error alerts (usually the maintainer's user id).
    alert_chat_id: int | None = None

    # Outgoing mail (Gmail app password). Without a password, mail is only logged.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    # In dev, every email goes here instead of its real recipients (None: log only).
    mail_dev_redirect: str | None = None

    # Meals: who receives the daily booking recap besides the "master" group.
    meals_recap_to: list[str] = []

    # CUPS destination for printing (None: default printer). In dev, jobs are only logged.
    printer: str | None = None

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ghislieri.sqlite3"


class ProductionGuardError(RuntimeError):
    pass


def check_production_guard(settings: Settings, marker: Path = PROD_MARKER) -> None:
    """Refuse to run the production bot anywhere but the production server, and vice versa."""
    bot_id = int(settings.bot_token.get_secret_value().split(":", 1)[0])
    uses_prod_bot = bot_id == PROD_BOT_ID
    if uses_prod_bot and not (settings.is_prod and marker.exists()):
        raise ProductionGuardError(
            f"Production bot token used with GS_ENV={settings.env} or without {marker}. "
            "Use the test bot token for development."
        )
    if settings.is_prod and not uses_prod_bot:
        raise ProductionGuardError("GS_ENV=prod but the token is not the production bot's.")
