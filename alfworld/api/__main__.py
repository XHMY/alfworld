"""CLI entry point: python -m alfworld.api"""

import argparse
import logging
import os

import uvicorn

from alfworld.api.app import create_app
from alfworld.api.config import ServerConfig


def main():
    parser = argparse.ArgumentParser(description="ALFWorld TextWorld Web API")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to ALFWorld base_config.yaml",
    )
    parser.add_argument(
        "--docker-image",
        default="alfworld-text:latest",
        help="Docker image for worker containers (default: alfworld-text:latest)",
    )
    parser.add_argument(
        "--data-volume",
        default="~/.cache/alfworld:/data:ro",
        help="Volume mount for game data (default: ~/.cache/alfworld:/data:ro)",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=64,
        help="Maximum concurrent sessions (default: 64)",
    )
    parser.add_argument(
        "--batch-window-ms",
        type=int,
        default=50,
        help="Batch window in milliseconds (default: 50)",
    )
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=120,
        help="Idle session timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Auto-detect project root: walk up from this file to find the repo root
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

    server_config = ServerConfig(
        alfworld_config_path=args.config,
        docker_image=args.docker_image,
        data_volume=args.data_volume,
        project_root=project_root,
        max_sessions=args.max_sessions,
        batch_window_ms=args.batch_window_ms,
        idle_timeout_s=args.idle_timeout,
        host=args.host,
        port=args.port,
    )

    app = create_app(server_config)

    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()
