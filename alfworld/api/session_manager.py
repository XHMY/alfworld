"""Session lifecycle and Docker container management."""

import asyncio
import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from typing import Dict, List, Optional

import docker

from alfworld.api.config import ServerConfig
from alfworld.api.models import TASK_TYPES
from alfworld.api.errors import (
    ContainerError,
    NoSlotsAvailable,
    SessionAlreadyDone,
    SessionNotFound,
)

logger = logging.getLogger("alfworld.api")


@dataclass
class Session:
    session_id: str
    container: object  # docker Container
    socket: object  # attached stream
    game_file: str
    observation: str
    admissible_commands: List[str]
    status: str = "active"  # "active" | "done"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _read_buffer: str = ""


class SessionManager:
    def __init__(
        self,
        docker_client: docker.DockerClient,
        config: ServerConfig,
        game_files: List[str],
    ):
        self.docker_client = docker_client
        self.config = config
        self.game_files = game_files
        self._sessions: Dict[str, Session] = {}
        self._semaphore = asyncio.Semaphore(config.max_sessions)
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    def get_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session

    async def create_session(
        self,
        game_file: Optional[str] = None,
        task_type: Optional[int] = None,
    ) -> Session:
        acquired = self._semaphore._value > 0
        if not acquired:
            raise NoSlotsAvailable(self.config.max_sessions)
        await self._semaphore.acquire()

        try:
            # Pick game file
            if game_file is None:
                candidates = self.game_files
                if task_type is not None and task_type in TASK_TYPES:
                    task_name = TASK_TYPES[task_type]
                    candidates = [
                        g for g in self.game_files if task_name in g
                    ]
                    if not candidates:
                        candidates = self.game_files
                game_file = random.choice(candidates)

            session_id = str(uuid.uuid4())

            # Start container
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                partial(self._start_container, session_id),
            )

            # Attach to stdin/stdout
            socket = await loop.run_in_executor(
                None,
                partial(self._attach_container, container),
            )

            session = Session(
                session_id=session_id,
                container=container,
                socket=socket,
                game_file=game_file,
                observation="",
                admissible_commands=[],
            )
            self._sessions[session_id] = session

            # Send init command — translate host path to container path
            container_game_file = self._to_container_path(game_file)
            init_cmd = {"cmd": "init", "game_file": container_game_file}
            response = await self.send_command(session, init_cmd)

            if response.get("status") != "ok":
                await self._kill_container(container)
                self._sessions.pop(session_id, None)
                self._semaphore.release()
                raise ContainerError(
                    f"Init failed: {response.get('message', 'unknown error')}"
                )

            session.observation = response.get("observation", "")
            session.admissible_commands = response.get("admissible_commands", [])

            return session

        except (NoSlotsAvailable, ContainerError):
            raise
        except Exception as e:
            self._semaphore.release()
            raise ContainerError(f"Failed to create session: {e}") from e

    def _to_container_path(self, host_path: str) -> str:
        """Translate a host data path to the corresponding container path."""
        host_data = self.config.data_host_path
        container_data = self.config.data_container_path
        if host_path.startswith(host_data):
            return container_data + host_path[len(host_data):]
        return host_path

    def _start_container(self, session_id: str):
        host_path = self.config.data_host_path
        container_path = self.config.data_container_path
        mode = self.config.data_volume_mode

        volumes = {host_path: {"bind": container_path, "mode": mode}}

        # Mount the api directory so worker.py is available inside the container
        project_root = self.config.project_root
        if project_root:
            api_host = os.path.join(project_root, "alfworld", "api")
            volumes[api_host] = {"bind": "/alfworld/alfworld/api", "mode": "ro"}

        container = self.docker_client.containers.run(
            self.config.docker_image,
            ["python", "-u", "alfworld/api/worker.py"],
            volumes=volumes,
            stdin_open=True,
            detach=True,
            auto_remove=True,
            labels={"alfworld-session": session_id},
        )
        return container

    def _attach_container(self, container):
        socket = container.attach_socket(
            params={"stdin": True, "stdout": True, "stderr": False, "stream": True}
        )
        return socket

    async def send_command(self, session: Session, command: dict) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self._send_command_sync, session, command),
        )

    def _send_command_sync(self, session: Session, command: dict) -> dict:
        payload = json.dumps(command) + "\n"
        try:
            self._write_to_stdin(session, payload)
            response_line = self._read_from_stdout(session)
            return json.loads(response_line)
        except Exception as e:
            return {"status": "error", "message": f"Communication error: {e}"}

    def _write_to_stdin(self, session: Session, payload: str):
        """Write to container stdin via the attached socket."""
        sock = session.socket._sock if hasattr(session.socket, '_sock') else session.socket
        sock.sendall(payload.encode("utf-8"))

    def _read_from_stdout(self, session: Session, timeout: float = 60.0) -> str:
        """Read a JSON line from container stdout via the attached socket."""
        import select
        import time as _time

        sock = session.socket._sock if hasattr(session.socket, '_sock') else session.socket
        sock.setblocking(False)

        buf = session._read_buffer
        deadline = _time.time() + timeout

        while True:
            remaining = deadline - _time.time()
            if remaining <= 0:
                raise TimeoutError("Timeout reading from container")

            # Check for complete line in buffer
            if "\n" in buf:
                line, rest = buf.split("\n", 1)
                session._read_buffer = rest
                # Docker stream framing: skip 8-byte header frames
                # The line might contain docker stream headers, try to extract JSON
                return self._extract_json_line(line)

            ready, _, _ = select.select([sock], [], [], min(remaining, 1.0))
            if ready:
                data = sock.recv(4096)
                if not data:
                    raise ConnectionError("Container closed connection")
                buf += self._decode_docker_stream(data)

    def _decode_docker_stream(self, data: bytes) -> str:
        """Decode Docker multiplexed stream data.

        Docker attach streams use an 8-byte header per frame:
        [stream_type(1), 0, 0, 0, size(4)] followed by the payload.
        """
        result = []
        pos = 0
        raw = data

        while pos < len(raw):
            if pos + 8 <= len(raw):
                # Try to parse as docker stream frame
                stream_type = raw[pos]
                if stream_type in (0, 1, 2):
                    size = int.from_bytes(raw[pos + 4 : pos + 8], "big")
                    if pos + 8 + size <= len(raw) and size > 0:
                        payload = raw[pos + 8 : pos + 8 + size]
                        if stream_type in (0, 1):  # stdin or stdout
                            result.append(payload.decode("utf-8", errors="replace"))
                        pos += 8 + size
                        continue

            # Fallback: treat rest as raw text
            result.append(raw[pos:].decode("utf-8", errors="replace"))
            break

        return "".join(result)

    def _extract_json_line(self, line: str) -> str:
        """Extract valid JSON from a line that may have docker framing artifacts."""
        line = line.strip()
        # Try as-is first
        try:
            json.loads(line)
            return line
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the line
        start = line.find("{")
        if start >= 0:
            candidate = line[start:]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        return line

    async def delete_all_sessions(self) -> list:
        """Kill all active sessions. Returns list of deleted session IDs."""
        session_ids = list(self._sessions.keys())
        deleted = []
        for sid in session_ids:
            try:
                await self.delete_session(sid)
                deleted.append(sid)
            except Exception:
                pass
        return deleted

    async def delete_session(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session is None:
            raise SessionNotFound(session_id)

        await self._kill_container(session.container)
        self._semaphore.release()

    async def _kill_container(self, container):
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, partial(container.kill))
        except Exception:
            # Container may already be stopped/removed
            pass

    async def start_cleanup_loop(self):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            to_remove = []
            for sid, session in self._sessions.items():
                idle = (now - session.last_active_at).total_seconds()
                if idle > self.config.idle_timeout_s:
                    to_remove.append(sid)

            for sid in to_remove:
                logger.info("Cleaning up idle session: %s", sid)
                try:
                    await self.delete_session(sid)
                except Exception:
                    pass

    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        session_ids = list(self._sessions.keys())
        for sid in session_ids:
            try:
                await self.delete_session(sid)
            except Exception:
                pass
