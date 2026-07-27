# ChatBots & Image Server

Run **image generation** and **roleplay-chat LLMs** locally and reach them from any device on
your LAN — including a phone — through a single web UI. No cloud, no per-token bills; everything
runs on your own machine.

One page gives you two tools:

- **🖼️ Images** — text-to-image generation (SDXL/Illustrious) driven by a local ComfyUI backend.
- **💬 Chat** — character roleplay powered by a local Ollama model, with SillyTavern/Chub
  character-card import, prompt presets, per-conversation personas, and conversation memory.

<!-- Add a screenshot here once you have one:
![UI](docs/screenshot.png)
-->

## Architecture

The only thing you open in a browser is **`image-fe`**, a small Dockerized web app. It proxies
everything to two backends that run **natively on the Windows host** (they need direct GPU
access, so they aren't containerized):

```
┌─────────────┐        ┌──────────────────────────────┐
│  Browser /  │  8080  │  image-fe  (Docker)           │
│    phone    │ ─────► │  FastAPI backend + React UI   │
└─────────────┘        └───────────┬──────────┬────────┘
                                    │ 8188     │ 11434
                            ┌───────▼───┐  ┌───▼────────┐
                            │ ComfyUI   │  │  Ollama    │
                            │ (images)  │  │  (chat)    │
                            └───────────┘  └────────────┘
                              native, GPU     native, GPU
```

| Service | Reached at (env var) | Purpose |
|---|---|---|
| **image-fe** | `http://localhost:8080` | the web UI + API you actually use |
| **ComfyUI** | `COMFYUI_URL` = `http://host.docker.internal:8188` | image generation |
| **Ollama** | `LLM_URL` = `http://host.docker.internal:11434` | roleplay chat (default model `nemomix-unleashed-12b`) |

### About ComfyUI (not included in this repo)

[**ComfyUI**](https://github.com/comfyanonymous/ComfyUI) is the image-generation engine. It is a
large, machine-specific install (an AMD GPU + ROCm runtime, a Python virtual environment, and
multi-gigabyte model checkpoints), so it is **intentionally excluded from this repository** — you
install it separately following the official project. `image-fe` simply talks to it over HTTP:
it injects your prompt/settings into an API-format copy of a txt2img workflow, submits it to
ComfyUI, relays live progress to the browser, and stores the results.

The one required tweak: ComfyUI listens on `127.0.0.1` by default, which Docker can't reach —
start it with `--listen 0.0.0.0` so the container (and your phone) can connect.

### About Ollama (not included in this repo)

[**Ollama**](https://ollama.com) serves the chat LLM. Install it, set
`OLLAMA_HOST=0.0.0.0:11434` so the container can reach it, and pull a roleplay-tuned model
(default `nemomix-unleashed-12b`, a Mistral-Nemo 12B finetune). `image-fe` assembles the full
prompt (character card + persona + history) and streams tokens back to the browser.

## Features

**Images tab** — generate from just a prompt, or open Advanced settings for size/steps/CFG/
sampler/seed. Live progress over Server-Sent Events, and a persistent gallery of every
generation (prompt, settings, seed, saved PNG).

**Chat tab** — create characters (description, personality, scenario, opening message, example
dialogue) or **import** a SillyTavern/Chub v2 character card. Per-conversation persona and
"current scene" note, switchable prompt presets, a summarize feature and message-level context
windowing to keep long chats coherent on small local models. Every character, conversation, and
message is saved and survives restarts.

## Requirements

- **Windows** host with **Docker Desktop**.
- An **AMD GPU + ROCm** for ComfyUI (image generation).
- **Ollama** installed for chat.
- ~16 GB VRAM comfortably runs image *or* chat; see `image-fe/README.md` for VRAM notes on
  running both.

## Quick start

1. Set up and start **ComfyUI** and **Ollama** on the host — see the one-time setup steps
   (firewall rules, `--listen`/`OLLAMA_HOST`, pulling a model) in **[`image-fe/README.md`](image-fe/README.md)**.
2. Build and run the web app:
   ```sh
   cd image-fe
   docker compose up --build -d
   ```
3. Open **http://localhost:8080** on the PC, or **http://<PC-LAN-IP>:8080** from a phone on the
   same Wi-Fi (find the LAN IP with `ipconfig`).

Prefer one command? **`start-all.ps1`** (repo root) checks each of Ollama, ComfyUI, and image-fe
and starts whichever isn't already running:

```powershell
powershell -File start-all.ps1
```

## Configuration

Defaults work out of the box. To point at non-default hosts/ports or a different model, copy
`image-fe/.env.example` to `image-fe/.env` and set `COMFYUI_URL`, `LLM_URL`, and `LLM_MODEL`
(must match the name from `ollama list`).

## Data persistence

All app data (image history + saved PNGs, and all chat characters/conversations/messages) lives
in the `fe-data` Docker volume, so it survives container rebuilds. To wipe everything:
`docker compose down -v`.

## Tech stack

FastAPI · React (Vite) · Docker · SQLite · Server-Sent Events · ComfyUI · Ollama

## License

[MIT](LICENSE)
