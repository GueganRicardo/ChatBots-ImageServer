"""Async client for talking to the ComfyUI HTTP + WebSocket API."""

import asyncio
import json

import httpx
import websockets


class ComfyClient:
    def __init__(self, base_url: str, client_id: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        ws_scheme = "wss" if self.base_url.startswith("https") else "ws"
        host = self.base_url.split("://", 1)[1]
        self.ws_url = f"{ws_scheme}://{host}/ws?clientId={client_id}"

        # per-prompt_id progress queues, filled by the background WS listener
        # and drained by the SSE handler in main.py
        self.queues: dict[str, asyncio.Queue] = {}

        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
        self._task: asyncio.Task | None = None
        self._stop = False

    async def start(self):
        self._stop = False
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self):
        self._stop = True
        if self._task:
            self._task.cancel()
        await self._http.aclose()

    def register(self, prompt_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.queues[prompt_id] = q
        return q

    def unregister(self, prompt_id: str):
        self.queues.pop(prompt_id, None)

    async def submit_prompt(self, workflow: dict) -> str:
        r = await self._http.post(
            "/prompt", json={"prompt": workflow, "client_id": self.client_id}
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(body["error"].get("message", "ComfyUI rejected the prompt"))
        return body["prompt_id"]

    async def get_history(self, prompt_id: str) -> dict:
        r = await self._http.get(f"/history/{prompt_id}")
        r.raise_for_status()
        return r.json()

    async def fetch_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        r = await self._http.get(
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": folder_type},
        )
        r.raise_for_status()
        return r.content

    async def get_object_info(self, node_class: str) -> dict:
        r = await self._http.get(f"/object_info/{node_class}")
        r.raise_for_status()
        return r.json()

    async def _listen_loop(self):
        # Keep one long-lived WS connection to ComfyUI, reconnecting on drop.
        while not self._stop:
            try:
                async with websockets.connect(self.ws_url, max_size=None, open_timeout=10) as ws:
                    async for raw in ws:
                        if isinstance(raw, (bytes, bytearray)):
                            continue  # binary preview frames, not needed
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        self._dispatch(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(2)

    def _dispatch(self, msg: dict):
        mtype = msg.get("type")
        data = msg.get("data") or {}
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            return
        q = self.queues.get(prompt_id)
        if q is None:
            return
        if mtype == "progress":
            q.put_nowait({"kind": "progress", "value": data.get("value", 0), "max": data.get("max", 1)})
        elif mtype == "executing":
            q.put_nowait({"kind": "executing", "node": data.get("node")})
        elif mtype == "execution_error":
            q.put_nowait(
                {"kind": "error", "message": data.get("exception_message", "ComfyUI execution error")}
            )
