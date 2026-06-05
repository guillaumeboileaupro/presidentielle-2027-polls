from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = Field(default="sqlite:///./data/polls.sqlite3", alias="DATABASE_URL")
    wikipedia_fr_url: str = Field(
        default=(
            "https://fr.wikipedia.org/wiki/"
            "Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027"
        ),
        alias="WIKIPEDIA_FR_URL",
    )
    wikipedia_en_url: str = Field(
        default="https://en.wikipedia.org/wiki/Opinion_polling_for_the_2027_French_presidential_election",
        alias="WIKIPEDIA_EN_URL",
    )
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    interim_dir: Path = Path("data/interim")
    processed_dir: Path = Path("data/processed")
    exports_dir: Path = Path("data/exports")
    historical_dir: Path = Path("data/historical")
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8501
    recency_lambda: float = 0.03
    default_election_date: str = "2027-04-11"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

