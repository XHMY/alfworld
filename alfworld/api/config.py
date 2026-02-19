"""Server configuration for the ALFWorld API."""

import os
from pathlib import Path

from pydantic import BaseModel, field_validator


class ServerConfig(BaseModel):
    alfworld_config_path: str
    docker_image: str = "alfworld-text:latest"
    data_volume: str = "~/.cache/alfworld:/data:ro"
    project_root: str = ""  # auto-detected if empty; mounted into container so worker.py is available
    max_sessions: int = 8
    batch_window_ms: int = 50
    idle_timeout_s: int = 600
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("data_volume")
    @classmethod
    def expand_data_volume(cls, v: str) -> str:
        if ":" in v:
            parts = v.split(":")
            parts[0] = str(Path(parts[0]).expanduser())
            return ":".join(parts)
        return str(Path(v).expanduser())

    @property
    def data_host_path(self) -> str:
        return self.data_volume.split(":")[0]

    @property
    def data_container_path(self) -> str:
        parts = self.data_volume.split(":")
        return parts[1] if len(parts) > 1 else "/data"

    @property
    def data_volume_mode(self) -> str:
        parts = self.data_volume.split(":")
        return parts[2] if len(parts) > 2 else "ro"
