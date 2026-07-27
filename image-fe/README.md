# image-fe

A small web front-end for local generation, so images and character roleplay chat can
both be used from a browser (including a phone on the same network) without opening the
full ComfyUI graph editor or a separate chat app.

- **Backend:** FastAPI, drives ComfyUI's HTTP + WebSocket API for images and Ollama's
  HTTP API for chat, streams both progress and chat tokens over SSE, keeps a persistent
  SQLite history of every generation plus every character/conversation/message.
- **Frontend:** React (Vite) with two tabs — **Images** and **Chat** — built and served
  by the backend as static files; it's all one Docker image.
- **Neither ComfyUI nor Ollama is containerized.** Both keep running natively on
  Windows (ComfyUI needs ROCm + the GPU driver stack; Ollama needs the same GPU), and
  this container talks to both over HTTP.

## One-time setup on the ComfyUI side

ComfyUI listens on `127.0.0.1` by default, which the Docker container can't reach.
This repo already adds `--listen 0.0.0.0` to `comfyui-rocm/comfyui-rocm.bat`'s
`PARAMS` line — just make sure ComfyUI is (re)started after that change.

The first time it starts listening on all interfaces, **Windows Firewall will likely
prompt** to allow the connection — allow it for **Private networks**.

## One-time setup on the Ollama (chat) side

1. Install [Ollama for Windows](https://ollama.com/download).
2. By default Ollama only listens on `127.0.0.1`, which the container can't reach.
   Make it listen on all interfaces: set the environment variable
   `OLLAMA_HOST=0.0.0.0:11434` (Windows: `setx OLLAMA_HOST "0.0.0.0:11434"`, then
   restart Ollama / sign out and back in so it takes effect) — same idea as the
   ComfyUI `--listen 0.0.0.0` change above.
3. Allow inbound **TCP 11434** on the **Private** firewall profile (same one-time step
   already done for ports 8080/8188):
   ```powershell
   New-NetFirewallRule -DisplayName "Ollama 11434" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Private,Domain
   ```
4. Pull a roleplay-tuned model, e.g.:
   ```sh
   ollama pull nemomix-unleashed-12b
   ```
   (a Mistral-Nemo 12B finetune, ~8 GB at Q4 — the spiritual successor to
   MythoMax-style RP models). If you'd rather run chat and image generation at the
   exact same time, an 8B RP finetune (e.g. an L3-8B Stheno variant) leaves more VRAM
   headroom. Whatever you pull, set `LLM_MODEL` (see below) to match the name shown by
   `ollama list`.

### VRAM note (16 GB shared with ComfyUI)

Using chat and image generation **sequentially** is fine — either model alone fits
comfortably, and ComfyUI already frees VRAM aggressively after each image
(`--cache-none --disable-smart-memory`). The one thing to know: Ollama keeps a model
"warm" in VRAM for a few minutes after your last message (`keep_alive`, default 5 min)
so replies stay fast — so generating an image *immediately* after chatting can briefly
need both models resident at once. If that ever causes problems: wait a few minutes, run
`ollama stop <model>` to unload it manually, or set a shorter `OLLAMA_KEEP_ALIVE`
(e.g. `60s`) in the Ollama environment.

## Running it

```sh
cd image-fe
docker compose up --build
```

This builds the image (Node stage builds the React app, Python stage runs it) and
starts the container, publishing port `8080` on all interfaces.

- On the PC: http://localhost:8080
- On your phone (same Wi-Fi): `http://<PC-LAN-IP>:8080` — find the PC's LAN IP with
  `ipconfig` (look for the IPv4 Address under your active adapter).

If ComfyUI or Ollama run somewhere other than their `host.docker.internal` defaults, or
you pulled a different model name, copy `.env.example` to `.env` and set `COMFYUI_URL` /
`LLM_URL` / `LLM_MODEL` accordingly.

## Data persistence

Everything lives in the `fe-data` Docker volume, independent of ComfyUI's own `output/`
folder: `history.db` (image generations + saved PNG copies) and `chat.db` (characters,
conversations, messages). It survives `docker compose down` / `up` and container
rebuilds. To wipe all of it:

```sh
docker compose down -v
```

## How it works — Images tab

1. The form's fields are pre-filled from the same defaults as
   `comfyui-rocm/user/default/workflows/First-images.json` (1024x1024, 20 steps,
   CFG 8, euler/normal, `waiIllustriousSDXL_v170.safetensors`) — you can generate with just
   a prompt, or open "Advanced settings" to change anything.
2. On Generate, the backend injects your values into an API-format copy of that
   workflow (`backend/workflow_template.json`) and submits it to ComfyUI's `/prompt`.
3. Progress is relayed to the browser over Server-Sent Events, backed by a
   persistent WebSocket connection the backend keeps open to ComfyUI's `/ws`.
4. On completion, the backend downloads the resulting image(s) from ComfyUI's
   `/view` endpoint, saves a copy into the volume, and records the generation (prompt,
   settings, seed, image paths) in SQLite. The phone/browser never talks to ComfyUI
   directly — everything is proxied through this container.

## How it works — Chat tab

1. Create a character (name, description, personality, scenario, opening message,
   example dialogue) or **import** a SillyTavern/Chub v2 character-card JSON.
2. Start a conversation with that character — its opening message (if any) seeds the
   chat. Conversations persist per character and survive restarts.
3. Sending a message posts it to `/api/chat/send` (which saves it to SQLite and builds
   the full message list — system prompt from the character card + optional persona,
   then conversation history), then subscribes to `/api/chat/stream/{id}`, an SSE
   endpoint that relays Ollama's token stream as it's generated.
4. The assistant's full reply is saved to SQLite once streaming completes. As with
   images, the phone/browser never talks to Ollama directly — everything is proxied
   through this container.
