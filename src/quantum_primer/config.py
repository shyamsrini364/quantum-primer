from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QP_", env_file=".env", extra="ignore")
    mode: Literal["demo", "live"] = "demo"
    api_key: SecretStr = SecretStr("")
    model_api_key: SecretStr = SecretStr("")
    model_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    chat_model: str = ""
    embedding_model: str = ""
    pinecone_api_key: SecretStr = SecretStr("")
    pinecone_index: str = "quantum-primer"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    namespace_prefix: str = "quantum-primer"
    manifest_path: Path = Path("data/index.json")
    top_k: int = Field(default=8, ge=1, le=30)
    context_k: int = Field(default=4, ge=1, le=10)
    min_dense_score: float = Field(default=0.35, ge=-1, le=1)
    cors_origins: list[str] = ["http://localhost:3000"]

    def require_live(self):
        required = ["model_api_key", "chat_model", "embedding_model", "pinecone_api_key"]
        missing = [
            name
            for name in required
            if not (
                getattr(self, name).get_secret_value()
                if isinstance(getattr(self, name), SecretStr)
                else getattr(self, name)
            )
        ]
        if missing:
            raise ValueError(
                "Missing live settings: " + ", ".join("QP_" + x.upper() for x in missing)
            )
