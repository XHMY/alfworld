"""FastAPI application factory and lifespan management."""

import json
import logging
import os
from contextlib import asynccontextmanager

import docker
import yaml

from fastapi import FastAPI

from alfworld.api.batcher import BatchCoordinator
from alfworld.api.config import ServerConfig
from alfworld.api.errors import register_error_handlers
from alfworld.api.models import TASK_TYPES
from alfworld.api.routes import router
from alfworld.api.session_manager import SessionManager

logger = logging.getLogger("alfworld.api")


def discover_game_files(alfworld_config_path: str) -> list:
    """Walk the data directory to find solvable game files.

    Re-implements the logic from AlfredTWEnv.collect_game_files without
    importing alfworld (which is only installed inside the Docker image).
    """
    with open(alfworld_config_path, "r") as f:
        config = yaml.safe_load(f)

    task_types = [TASK_TYPES[t] for t in config["env"]["task_types"] if t in TASK_TYPES]

    data_paths = []
    for key in ("data_path", "eval_id_data_path", "eval_ood_data_path"):
        path = config["dataset"].get(key)
        if path:
            data_paths.append(os.path.expandvars(path))

    game_files = []
    for data_path in data_paths:
        if not os.path.isdir(data_path):
            logger.warning("Data path does not exist: %s", data_path)
            continue

        for root, dirs, files in os.walk(data_path, topdown=False):
            if "traj_data.json" not in files:
                continue

            game_file_path = os.path.join(root, "game.tw-pddl")
            if not os.path.exists(game_file_path):
                continue

            if "movable" in root or "Sliced" in root:
                continue

            # Check task type
            traj_path = os.path.join(root, "traj_data.json")
            try:
                with open(traj_path, "r") as f:
                    traj_data = json.load(f)
                if traj_data.get("task_type") not in task_types:
                    continue
            except Exception:
                continue

            # Check solvability
            try:
                with open(game_file_path, "r") as f:
                    gamedata = json.load(f)
                if not gamedata.get("solvable", False):
                    continue
            except Exception:
                continue

            game_files.append(game_file_path)

    return game_files


def create_app(server_config: ServerConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting ALFWorld API server...")

        # Discover game files
        logger.info("Discovering game files from %s", server_config.alfworld_config_path)
        game_files = discover_game_files(server_config.alfworld_config_path)
        logger.info("Found %d game files", len(game_files))
        app.state.game_files = game_files

        # Create Docker client
        docker_client = docker.from_env()
        app.state.docker_client = docker_client

        # Create session manager
        sm = SessionManager(
            docker_client=docker_client,
            config=server_config,
            game_files=game_files,
        )
        app.state.session_manager = sm

        # Create batch coordinator
        batcher = BatchCoordinator(
            session_manager=sm,
            batch_window_ms=server_config.batch_window_ms,
        )
        app.state.batcher = batcher

        # Start cleanup loop
        await sm.start_cleanup_loop()

        logger.info(
            "ALFWorld API ready: %d games, max %d sessions",
            len(game_files),
            server_config.max_sessions,
        )

        yield

        # Shutdown
        logger.info("Shutting down ALFWorld API server...")
        await sm.shutdown()
        docker_client.close()

    app = FastAPI(
        title="ALFWorld TextWorld API",
        description="Web API for ALFWorld TextWorld environments with Docker-based sessions",
        version="0.1.0",
        lifespan=lifespan,
    )

    register_error_handlers(app)
    app.include_router(router)

    return app
