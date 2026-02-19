#!/usr/bin/env python
"""
API example: Interact with ALFWorld via the Web API

Demonstrates single-session gameplay and concurrent multi-session usage.
Sessions are wrapped in context managers so containers are always cleaned up,
even if the script crashes mid-run.

Prerequisites:
    1. Start the API server:
       python -m alfworld.api --config configs/base_config.yaml
    2. Run this example:
       python examples/api_example.py [--base-url http://localhost:8000]
"""

import argparse
import asyncio
import random
import sys
import time

import aiohttp
import requests


class Session:
    """Sync context manager that creates a session on enter and deletes it on exit."""

    def __init__(self, base_url: str, **create_kwargs):
        self.base_url = base_url
        self.create_kwargs = create_kwargs
        self.data = None
        self.session_id = None

    def __enter__(self):
        r = requests.post(f"{self.base_url}/sessions", json=self.create_kwargs)
        r.raise_for_status()
        self.data = r.json()
        self.session_id = self.data["session_id"]
        return self.data

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session_id:
            try:
                requests.delete(f"{self.base_url}/sessions/{self.session_id}")
            except Exception:
                pass
        return False


class AsyncSessionGroup:
    """Async context manager that creates N sessions concurrently and deletes them on exit."""

    def __init__(self, http: aiohttp.ClientSession, base_url: str, n: int):
        self.http = http
        self.base_url = base_url
        self.n = n
        self.sessions = []

    async def __aenter__(self):
        creates = [self.http.post(f"{self.base_url}/sessions", json={}) for _ in range(self.n)]
        responses = await asyncio.gather(*creates, return_exceptions=True)
        rejected = 0
        for resp in responses:
            if isinstance(resp, Exception):
                rejected += 1
                continue
            try:
                data = await resp.json()
                if "session_id" in data:
                    self.sessions.append(data)
                else:
                    rejected += 1
                    error_code = data.get("error_code", "unknown")
                    print(f"  Session rejected: {data.get('detail', error_code)}")
            except Exception:
                rejected += 1
        if rejected:
            print(f"  ({rejected}/{self.n} sessions rejected — server at capacity)")
        return self.sessions

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        deletes = [
            self.http.delete(f"{self.base_url}/sessions/{s['session_id']}")
            for s in self.sessions
        ]
        await asyncio.gather(*deletes, return_exceptions=True)
        return False


def single_session_demo(base_url: str):
    """Run one session with a random agent, using synchronous requests."""
    print("=== Single Session Demo ===\n")

    with Session(base_url) as session:
        sid = session["session_id"]
        print(f"Session: {sid[:8]}...")
        print(f"Game:    {session['game_file'].split('/')[-2]}")
        print(f"Task:    {session['observation'].split('Your task is to: ')[-1]}")
        print()

        admissible = session["admissible_commands"]
        max_steps = 30

        for step in range(1, max_steps + 1):
            action = random.choice(admissible) if admissible else "look"
            r = requests.post(
                f"{base_url}/sessions/{sid}/step", json={"action": action}
            )
            r.raise_for_status()
            result = r.json()

            obs_short = result["observation"][:100]
            print(f"  Step {step:2d}: {action}")
            print(f"           -> {obs_short}")

            if result["done"]:
                outcome = "WON" if result["won"] else "LOST"
                print(f"\n  Game over: {outcome} (score={result['score']}) in {step} steps")
                break

            admissible = result["admissible_commands"]
        else:
            print(f"\n  Stopped after {max_steps} steps")

    print()


async def concurrent_sessions_demo(base_url: str, n: int = 3):
    """Run N sessions in parallel, each taking random actions."""
    print(f"=== Concurrent Sessions Demo ({n} sessions) ===\n")

    async with aiohttp.ClientSession() as http:
        t0 = time.time()
        async with AsyncSessionGroup(http, base_url, n) as sessions:
            print(f"Created {len(sessions)} sessions in {time.time() - t0:.2f}s")

            for s in sessions:
                task = s["observation"].split("Your task is to: ")[-1]
                print(f"  {s['session_id'][:8]}... -> {task[:60]}")
            print()

            # Run all sessions for a few steps
            states = {s["session_id"]: s["admissible_commands"] for s in sessions}
            active = set(states.keys())
            max_steps = 10

            for step in range(1, max_steps + 1):
                if not active:
                    break

                actions = {}
                for sid in active:
                    cmds = states[sid]
                    actions[sid] = random.choice(cmds) if cmds else "look"

                t1 = time.time()
                step_coros = [
                    http.post(
                        f"{base_url}/sessions/{sid}/step",
                        json={"action": act},
                    )
                    for sid, act in actions.items()
                ]
                responses = await asyncio.gather(*step_coros)
                results = {
                    sid: await r.json()
                    for sid, r in zip(actions.keys(), responses)
                }
                elapsed = time.time() - t1

                print(f"Step {step:2d} ({len(active)} sessions, {elapsed:.3f}s):")
                done_this_round = []
                for sid, res in results.items():
                    tag = sid[:8]
                    obs = res["observation"][:60]
                    print(f"  {tag}... [{actions[sid][:30]}] -> {obs}")
                    if res["done"]:
                        outcome = "WON" if res["won"] else "LOST"
                        print(f"           ** {outcome} **")
                        done_this_round.append(sid)
                    else:
                        states[sid] = res["admissible_commands"]

                for sid in done_this_round:
                    active.discard(sid)
                print()

        print(f"Cleaned up {len(sessions)} sessions")

        # Final health check
        r = await http.get(f"{base_url}/health")
        health = await r.json()
        print(f"Health: active_sessions={health['active_sessions']}")


def main():
    parser = argparse.ArgumentParser(description="ALFWorld API example")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=3,
        help="Number of concurrent sessions (default: 3)",
    )
    args = parser.parse_args()

    # Verify server is running
    try:
        r = requests.get(f"{args.base_url}/health")
        r.raise_for_status()
        health = r.json()
        print(f"Server OK: {health['available_games']} games, "
              f"max {health['max_sessions']} sessions\n")
    except requests.ConnectionError:
        print(f"Cannot connect to {args.base_url}. Is the server running?")
        print("Start it with: python -m alfworld.api --config configs/base_config.yaml")
        sys.exit(1)

    single_session_demo(args.base_url)
    asyncio.run(concurrent_sessions_demo(args.base_url, n=args.concurrent))


if __name__ == "__main__":
    main()
