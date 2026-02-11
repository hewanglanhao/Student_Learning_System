from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "user_profiles_db"
    practice_collection: str = "practice"
    user_collection: str = "user_profiles"

    model_path: str | None = None
    knowledge_points_path: str | None = None

    model_config = SettingsConfigDict(env_prefix="DKT_", protected_namespaces=("settings_",))

    def resolved_model_path(self) -> Path:
        if self.model_path:
            return Path(self.model_path)
        return Path(__file__).resolve().parents[1] / "dkt_model.pt"

    def resolved_knowledge_points_path(self) -> Path:
        if self.knowledge_points_path:
            return Path(self.knowledge_points_path)
        return Path(__file__).resolve().parents[2] / "最终结果.py"


settings = Settings()
