"""Pydantic request/response schemas for the ALFWorld API."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

# Duplicated from alfworld.agents.environment.alfred_tw_env so the host
# doesn't need alfworld installed (it runs inside Docker containers only).
TASK_TYPES = {
    1: "pick_and_place_simple",
    2: "look_at_obj_in_light",
    3: "pick_clean_then_place_in_recep",
    4: "pick_heat_then_place_in_recep",
    5: "pick_cool_then_place_in_recep",
    6: "pick_two_obj_and_place",
}


# -- Requests --

class CreateSessionRequest(BaseModel):
    game_file: Optional[str] = None
    task_type: Optional[int] = None


class StepRequest(BaseModel):
    action: str


# -- Responses --

class SessionResponse(BaseModel):
    session_id: str
    game_file: str
    observation: str
    admissible_commands: List[str]
    status: str
    created_at: datetime
    last_active_at: datetime


class StepResponse(BaseModel):
    session_id: str
    observation: str
    score: float
    done: bool
    won: bool
    admissible_commands: List[str]


class GameListResponse(BaseModel):
    games: List[str]
    total: int


class TaskTypesResponse(BaseModel):
    task_types: Dict[int, str]


class HealthResponse(BaseModel):
    status: str
    active_sessions: int
    max_sessions: int
    available_games: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
