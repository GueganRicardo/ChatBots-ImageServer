"""Async client for talking to Ollama's HTTP API (chat completion + model list)."""

import json
from typing import AsyncIterator

import httpx


class LLMClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(120.0, connect=10.0))

    async def close(self):
        await self._http.aclose()

    async def list_models(self) -> list[str]:
        r = await self._http.get("/api/tags")
        r.raise_for_status()
        body = r.json()
        return [m["name"] for m in body.get("models", [])]

    async def stream_chat(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        keep_alive: str | int | None = None,
    ) -> AsyncIterator[dict]:
        """POST /api/chat with stream=true; yields {"content": token} deltas, then a
        final {"done": True} marker (or {"error": message} on failure)."""
        payload = {"model": model, "messages": messages, "stream": True}
        if options:
            payload["options"] = options
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        try:
            async with self._http.stream("POST", "/api/chat", json=payload) as r:
                if r.status_code >= 400:
                    body = await r.aread()
                    try:
                        message = json.loads(body).get("error", body.decode(errors="replace"))
                    except Exception:
                        message = body.decode(errors="replace")
                    yield {"error": message or "Ollama returned an error"}
                    return

                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if chunk.get("error"):
                        yield {"error": chunk["error"]}
                        return

                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield {"content": content}

                    if chunk.get("done"):
                        yield {
                            "done": True,
                            "prompt_eval_count": chunk.get("prompt_eval_count"),
                            "eval_count": chunk.get("eval_count"),
                        }
                        return
        except httpx.HTTPError as e:
            yield {"error": f"Could not reach Ollama: {e}"}
