from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from typing import Any

try:
    import websockets
except ImportError:  # pragma: no cover - handled by the UI at runtime.
    websockets = None


OnlineEventHandler = Callable[[str, dict[str, Any]], None]
OnlineErrorHandler = Callable[[str], None]


class OnlineClient:
    def __init__(
        self,
        url: str,
        first_action: str,
        first_data: dict[str, Any],
        on_event: OnlineEventHandler,
        on_error: OnlineErrorHandler,
    ) -> None:
        if websockets is None:
            raise RuntimeError("缺少 websockets 依赖，请先运行：pip install -r requirements.txt")
        self.url = url
        self.first_action = first_action
        self.first_data = first_data
        self.on_event = on_event
        self.on_error = on_error
        self.loop: asyncio.AbstractEventLoop | None = None
        self.websocket: Any = None
        self.thread: threading.Thread | None = None
        self.closed = False

    def start(self) -> None:
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.thread.start()

    def send(self, action: str, data: dict[str, Any] | None = None) -> None:
        if self.loop is None or self.websocket is None:
            self.on_error("服务器还没有连接完成。")
            return
        payload = {"action": action, "data": data or {}}
        asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(payload, ensure_ascii=False)), self.loop)

    def close(self) -> None:
        self.closed = True
        if self.loop is not None and self.websocket is not None:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            if not self.closed:
                self.on_error(str(exc))

    async def _run(self) -> None:
        self.loop = asyncio.get_running_loop()
        async with websockets.connect(self.url) as websocket:
            self.websocket = websocket
            await websocket.send(json.dumps({"action": self.first_action, "data": self.first_data}, ensure_ascii=False))
            async for raw_message in websocket:
                message = json.loads(raw_message)
                self.on_event(str(message.get("event")), message.get("data") or {})
