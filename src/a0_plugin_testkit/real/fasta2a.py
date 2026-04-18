"""In-process FastA2A server with a scripted worker, for component tests.

Use this when a test needs a real FastA2A endpoint over real HTTP (authed with
real bearer tokens, real JSON-RPC wire shapes) but the responses should be
deterministic rather than driven by a real A0 agent loop.

Example:

    async with scripted_a2a_server(scripts={"17 times 23": "391"}) as (url, worker, app):
        async with httpx.AsyncClient() as http:
            client = A2AClient(base_url=url, http_client=http)
            resp = await client.send_message(...)

The scripted worker runs in the uvicorn event loop via a custom lifespan, so
anyio task groups compose cleanly with pytest-asyncio.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import uvicorn
from fasta2a import FastA2A, Worker
from fasta2a.broker import InMemoryBroker
from fasta2a.schema import Artifact, Message, Skill, TaskSendParams
from fasta2a.storage import InMemoryStorage


@dataclass
class ScriptedWorker(Worker):
    """Worker that returns canned responses keyed by substring of the user's text.

    If no substring matches, replies with `default`. Slow tasks can be simulated
    via `delays` (seconds per substring key).
    """

    broker: InMemoryBroker
    storage: InMemoryStorage
    scripts: dict[str, str] = field(default_factory=dict)
    delays: dict[str, float] = field(default_factory=dict)
    default: str = "I don't know."
    seen: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        Worker.__init__(self, broker=self.broker, storage=self.storage)

    async def run_task(self, params: TaskSendParams) -> None:
        task_id = params["id"]
        message = params["message"]
        user_text = "\n".join(
            p.get("text", "")
            for p in message.get("parts", [])
            if p.get("kind") == "text"
        )
        self.seen.append(user_text)

        # optional delay keyed by substring
        for key, sec in self.delays.items():
            if key.lower() in user_text.lower():
                await asyncio.sleep(sec)
                break

        reply = self.default
        for key, resp in self.scripts.items():
            if key.lower() in user_text.lower():
                reply = resp
                break

        agent_msg: Message = {  # type: ignore[typeddict-item]
            "role": "agent",
            "parts": [{"kind": "text", "text": reply}],
            "kind": "message",
            "message_id": str(uuid.uuid4()),
        }
        await self.storage.update_task(
            task_id=task_id,
            state="completed",
            new_messages=[agent_msg],
        )
        self.completed.append(task_id)

    async def cancel_task(self, params: Any) -> None:
        task_id = params["id"]
        self.cancelled.append(task_id)
        await self.storage.update_task(task_id=task_id, state="canceled")

    def build_message_history(self, history: Any) -> list[Message]:
        return []

    def build_artifacts(self, result: Any) -> list[Artifact]:
        return []


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_port(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return
        except OSError:
            await asyncio.sleep(0.05)
    raise TimeoutError(f"server on {host}:{port} never became ready")


@contextlib.asynccontextmanager
async def scripted_a2a_server(
    scripts: dict[str, str] | None = None,
    delays: dict[str, float] | None = None,
    default: str = "I don't know.",
) -> AsyncIterator[tuple[str, ScriptedWorker, FastA2A]]:
    """Context manager yielding (base_url, worker, app) for a running FastA2A."""
    storage = InMemoryStorage()
    broker = InMemoryBroker()
    worker = ScriptedWorker(
        broker=broker,
        storage=storage,
        scripts=scripts or {},
        delays=delays or {},
        default=default,
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: FastA2A) -> AsyncIterator[None]:
        async with app.task_manager, worker.run():
            yield

    app = FastA2A(
        storage=storage,
        broker=broker,
        name="scripted",
        description="scripted test worker",
        version="0.0.1",
        skills=[
            Skill(  # type: ignore[typeddict-item]
                id="scripted",
                name="Scripted",
                description="returns canned text",
                tags=["test"],
                examples=["hello"],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
        lifespan=lifespan,
    )

    port = _free_port()
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        loop="asyncio",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    try:
        await _wait_port("127.0.0.1", port)
        yield f"http://127.0.0.1:{port}", worker, app
    finally:
        server.should_exit = True
        with contextlib.suppress(Exception):
            await asyncio.wait_for(serve_task, timeout=5.0)


__all__ = ("ScriptedWorker", "scripted_a2a_server")
