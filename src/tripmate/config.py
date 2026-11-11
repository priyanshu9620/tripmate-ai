"""Settings. `.env` is loaded into os.environ too, because provider SDKs read the environment directly."""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "fake"
    llm_model: str = "fake"
    database_url: str = "postgresql://tm:tm@localhost:5433/tripmate"
    tools_mode: str = "offline"  # offline (fixtures) | live (Open-Meteo / Nominatim / Overpass)
    tools_timeout_s: float = 8.0
    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()
