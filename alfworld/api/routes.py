"""API endpoint handlers."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from alfworld.api.errors import SessionAlreadyDone
from alfworld.api.models import (
    TASK_TYPES,
    CreateSessionRequest,
    GameListResponse,
    HealthResponse,
    SessionResponse,
    StepRequest,
    StepResponse,
    TaskTypesResponse,
)

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: Request, body: CreateSessionRequest = None):
    if body is None:
        body = CreateSessionRequest()

    sm = request.app.state.session_manager
    session = await sm.create_session(
        game_file=body.game_file,
        task_type=body.task_type,
    )

    return SessionResponse(
        session_id=session.session_id,
        game_file=session.game_file,
        observation=session.observation,
        admissible_commands=session.admissible_commands,
        status=session.status,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
    )


@router.delete("/sessions")
async def delete_all_sessions(request: Request):
    sm = request.app.state.session_manager
    deleted = await sm.delete_all_sessions()
    return {"status": "ok", "deleted": deleted, "count": len(deleted)}


@router.post("/sessions/{session_id}/step", response_model=StepResponse)
async def step_session(request: Request, session_id: str, body: StepRequest):
    sm = request.app.state.session_manager
    batcher = request.app.state.batcher

    session = sm.get_session(session_id)
    if session.status == "done":
        raise SessionAlreadyDone(session_id)

    result = await batcher.submit_step(session, body.action)

    if result.get("status") != "ok":
        from alfworld.api.errors import ContainerError
        raise ContainerError(result.get("message", "Step failed"))

    done = result.get("done", False)
    if done:
        session.status = "done"

    return StepResponse(
        session_id=session_id,
        observation=result.get("observation", ""),
        score=result.get("score", 0.0),
        done=done,
        won=result.get("won", False),
        admissible_commands=result.get("admissible_commands", []),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    sm = request.app.state.session_manager
    await sm.delete_session(session_id)
    return {"status": "ok", "session_id": session_id}


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(request: Request, session_id: str):
    sm = request.app.state.session_manager
    session = sm.get_session(session_id)

    return SessionResponse(
        session_id=session.session_id,
        game_file=session.game_file,
        observation=session.observation,
        admissible_commands=session.admissible_commands,
        status=session.status,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
    )


@router.get("/games", response_model=GameListResponse)
async def list_games(request: Request):
    game_files = request.app.state.game_files
    return GameListResponse(games=game_files, total=len(game_files))


@router.get("/task-types", response_model=TaskTypesResponse)
async def list_task_types():
    return TaskTypesResponse(task_types=TASK_TYPES)


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    sm = request.app.state.session_manager
    game_files = request.app.state.game_files
    return HealthResponse(
        status="ok",
        active_sessions=sm.active_session_count,
        max_sessions=sm.config.max_sessions,
        available_games=len(game_files),
    )
