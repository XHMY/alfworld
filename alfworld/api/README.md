# ALFWorld TextWorld Web API

A FastAPI server that wraps ALFWorld TextWorld environments. Each session runs in its own Docker container, communicating via stdin/stdout JSON lines protocol.

## Architecture

```
                ┌──────────────────────────┐
 Client A ────► │      FastAPI Server       │
 Client B ────► │  SessionManager + Batcher │
 Client C ────► │       (docker-py)         │
                └──┬────────┬────────┬──────┘
                   │        │        │  stdin/stdout
                ┌──▼──┐  ┌──▼──┐  ┌──▼──┐
                │ C1  │  │ C2  │  │ C3  │  Docker containers
                └─────┘  └─────┘  └─────┘  (alfworld-text)
```

- One Docker container per session, running `worker.py`
- Auto-batching dispatches concurrent step requests in parallel
- Containers are ephemeral — killed and auto-removed on session end

## Quick Start

```bash
# Install API server dependencies (host only, no alfworld needed)
pip install -r requirements-api.txt

# Start the server
python -m alfworld.api --config configs/base_config.yaml

# Health check
curl http://localhost:8000/health
```

Swagger docs available at `http://localhost:8000/docs`.

## API Endpoints

| Method   | Path                      | Description                          |
|----------|---------------------------|--------------------------------------|
| `POST`   | `/sessions`               | Create session (start container)     |
| `POST`   | `/sessions/{id}/step`     | Take an action                       |
| `GET`    | `/sessions/{id}`          | Get session status                   |
| `DELETE` | `/sessions`               | Kill all sessions                    |
| `DELETE` | `/sessions/{id}`          | End session (kill container)         |
| `GET`    | `/games`                  | List available game files            |
| `GET`    | `/task-types`             | List task type ID-to-name mapping    |
| `GET`    | `/health`                 | Health check                         |

## CLI Options

```
python -m alfworld.api \
    --config configs/base_config.yaml \
    --docker-image alfworld-text:latest \
    --data-volume ~/.cache/alfworld:/data:ro \
    --max-sessions 8 \
    --batch-window-ms 50 \
    --idle-timeout 600 \
    --host 0.0.0.0 \
    --port 8000
```

## Example Usage

See [`examples/api_example.py`](../../examples/api_example.py) for a full working example including concurrent sessions.

```python
import requests

BASE = "http://localhost:8000"

# Create a session
r = requests.post(f"{BASE}/sessions", json={"task_type": 1})
session = r.json()
sid = session["session_id"]
print(session["observation"])

# Take actions
r = requests.post(f"{BASE}/sessions/{sid}/step", json={"action": "look"})
result = r.json()
print(result["observation"], result["admissible_commands"])

# End session
requests.delete(f"{BASE}/sessions/{sid}")

# Kill all sessions (useful for cleanup after crashes)
requests.delete(f"{BASE}/sessions")
```

### Kill all sessions via curl

```bash
curl -X DELETE http://localhost:8000/sessions
```
