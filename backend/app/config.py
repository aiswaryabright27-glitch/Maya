from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(ge=1024, le=65535)
    backend_token: SecretStr = Field(min_length=32)
    mode: Literal["mock"] = "mock"
    data_dir: Path
    gnani_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    llm_provider: Literal["auto", "gemini", "openai"] = "auto"
    llm_model: str = "gemini-3.1-flash-lite"

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / "backend" / ".env", override=False)
        data_dir = os.getenv("MAYA_DATA_DIR")
        if not data_dir:
            local_app_data = os.getenv("LOCALAPPDATA")
            data_dir = str(Path(local_app_data) / "Maya") if local_app_data else str(Path.home() / ".maya")
        try:
            return cls(
                host=os.getenv("MAYA_HOST", "127.0.0.1"),
                port=int(os.getenv("MAYA_PORT", "8765")),
                backend_token=os.getenv("MAYA_BACKEND_TOKEN", ""),
                mode=os.getenv("MAYA_MODE", "mock").lower(),
                data_dir=Path(data_dir).expanduser(),
                gnani_api_key=os.getenv("GNANI_API_KEY") or None,
                openai_api_key=os.getenv("OPENAI_API_KEY") or None,
                gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
                llm_provider=os.getenv("MAYA_LLM_PROVIDER", "auto").lower(),
                llm_model=os.getenv("MAYA_LLM_MODEL", "gemini-3.1-flash-lite"),
            )
        except (ValueError, ValidationError):
            # Pydantic errors include the submitted input values. Do not include them in
            # a startup exception that may be shown by a launcher or captured in logs.
            raise RuntimeError("Invalid Maya environment configuration; check MAYA_HOST, MAYA_PORT, MAYA_BACKEND_TOKEN, MAYA_MODE, and MAYA_DATA_DIR.") from None

    @property
    def database_path(self) -> Path:
        return self.data_dir / "maya.db"

