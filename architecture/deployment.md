# Deployment Architecture

> **Deployment topology, container orchestration, and infrastructure design for Odysseus.**

---

## 1. Deployment Topology

### 1.1 Docker Compose (Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER HOST                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              odysseus-network (bridge)                 │   │
│  │                                                       │   │
│  │  ┌──────────────┐  ┌──────────┐  ┌──────────┐       │   │
│  │  │  odysseus    │  │ chromadb │  │ searxng  │       │   │
│  │  │  (app:7000)  │  │ (:8000)  │  │ (:8080)  │       │   │
│  │  │              │  │          │  │          │       │   │
│  │  │ Python 3.12  │  │ ChromaDB │  │ SearXNG  │       │   │
│  │  │ FastAPI       │  │ Vector   │  │ Privacy   │       │   │
│  │  │ Uvicorn       │  │ Store    │  │ Search    │       │   │
│  │  └──────┬───────┘  └──────────┘  └──────────┘       │   │
│  │         │                                             │   │
│  │  ┌──────┴───────┐                                     │   │
│  │  │    ntfy      │                                     │   │
│  │  │   (:8091)    │                                     │   │
│  │  │ Push Notifs  │                                     │   │
│  │  └──────────────┘                                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Bind Mounts:                                                │
│  ├── ./data:/app/data          (persistent app data)         │
│  ├── ./logs:/app/logs          (application logs)            │
│  ├── ./data/huggingface:/app/.cache/huggingface (models)    │
│  ├── ./data/local:/app/.local   (pip packages for engines)  │
│  └── ./data/ssh:/app/.ssh       (SSH keys for remote)       │
│                                                              │
│  Port Bindings (all 127.0.0.1 by default):                   │
│  ├── ${APP_BIND}:${APP_PORT} → container:7000                │
│  ├── 127.0.0.1:8080 → searxng:8080                          │
│  ├── 127.0.0.1:8091 → ntfy:8091                             │
│  └── 127.0.0.1:8100 → chromadb:8000 (debug only)           │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 GPU Overlays

```
NVIDIA GPU:
  docker-compose.yml + docker/gpu.nvidia.yml
  ├── deploy.resources.reservations.devices:
  │     └── driver: nvidia, count: 1, capabilities: [gpu]
  └── Environment: NVIDIA_VISIBLE_DEVICES=all

AMD GPU:
  docker-compose.yml + docker/gpu.amd.yml
  ├── devices:
  │     ├── /dev/kfd:/dev/kfd
  │     └── /dev/dri:/dev/dri
  └── group_add: ${RENDER_GID}
```

---

## 2. Container Architecture

### 2.1 Dockerfile
```
Base: python:3.12-slim
├── System deps: build-essential, cmake, git, tmux,
│     openssh-client, nodejs, npm, gosu, curl
├── Python deps: requirements.txt (pip install)
├── App code: COPY . .
├── Data dirs: mkdir -p data logs services/cache/search
├── Entrypoint: docker/entrypoint.sh
│     ├── Repair ownership: chown PUID:PGID /app/data /app/logs
│     └── Drop privileges: exec gosu $PUID:$PGID uvicorn ...
└── EXPOSE 7000
```

### 2.2 Privilege Dropping
```
Entrypoint sequence:
1. Root: chown PUID:PGID on bind-mounted directories
   (so host user can read/write data/ and logs/)
2. Root: exec gosu $PUID:$PGID uvicorn app:app
3. Uvicorn runs as non-root user (default 1000:1000)

Without this: root-owned files on bind mounts → EPERM on host
```

---

## 3. Volume Strategy

```
Persistent Volumes (survive container recreation):

./data/                 → /app/data/
  ├── app.db            SQLite database (sessions, messages, documents)
  ├── auth.json         User accounts and passwords
  ├── sessions.json     Active session tokens
  ├── memory.json       Persistent memories
  ├── settings.json     Application settings
  ├── features.json     Feature flags
  ├── presets.json      Chat presets
  ├── user_prefs.json   Per-user UI preferences
  ├── uploads/          User file uploads
  ├── personal_docs/    Personal RAG documents
  ├── generated_images/ AI-generated images
  ├── tts_cache/        Cached TTS audio
  ├── mail-attachments/ Email attachment cache
  ├── skills/           Agent skill definitions
  ├── chroma/           ChromaDB persistent storage
  └── deep_research/    Research job cache

./data/huggingface/     → /app/.cache/huggingface/
  └── Model files (GGUF, safetensors, etc.)

./data/local/           → /app/.local/
  └── pip --user packages (vLLM, llama-cpp-python, etc.)

./data/ssh/             → /app/.ssh/
  └── SSH keys for Cookbook remote servers

./logs/                 → /app/logs/
  └── Application log files
```

---

## 4. Environment Configuration

### 4.1 Core Settings
```
APP_BIND            = 127.0.0.1     # Network interface to bind
APP_PORT            = 7000          # Host port
AUTH_ENABLED        = true          # Require authentication
LOCALHOST_BYPASS    = false         # Dev-only auth bypass
SECURE_COOKIES      = false         # Set true behind HTTPS proxy
DATABASE_URL        = sqlite:///./data/app.db
```

### 4.2 LLM Configuration
```
LLM_HOST            = localhost     # Default LLM server
LLM_HOSTS           =               # Comma-separated list for discovery
OPENAI_API_KEY      =               # OpenAI API key
OLLAMA_BASE_URL     =               # Ollama server URL
RESEARCH_LLM_ENDPOINT =            # Separate LLM for research
HF_TOKEN            =               # HuggingFace token
```

### 4.3 Service Configuration
```
CHROMADB_HOST       = chromadb      # ChromaDB hostname (Docker service name)
CHROMADB_PORT       = 8000          # ChromaDB port
SEARXNG_INSTANCE    = http://searxng:8080
EMBEDDING_URL       =               # Custom embeddings endpoint
EMBEDDING_MODEL     =               # Custom embedding model
FASTEMBED_MODEL     = sentence-transformers/all-MiniLM-L6-v2
```

### 4.4 Background Services
```
ODYSSEUS_INPROCESS_POLLERS = 1     # Enable in-process email polling
ODYSSEUS_INPROCESS_TASKS   = 1     # Enable in-process task scheduler
ODYSSEUS_SCRIPT_HOST       = localhost
CLEANUP_INTERVAL_HOURS     = 24    # Orphaned resource cleanup interval
```

### 4.5 Search API Keys
```
DATA_BRAVE_API_KEY  =               # Brave Search API key
GOOGLE_API_KEY      =               # Google Custom Search API key
GOOGLE_PSE_CX       =               # Google Programmable Search Engine ID
TAVILY_API_KEY      =               # Tavily Search API key
SERPER_API_KEY      =               # Serper.dev API key
```

---

## 5. Native Deployment

### 5.1 Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

### 5.2 macOS (Apple Silicon)
```bash
./start-macos.sh
# Port 7860 (AirPlay often holds 7000)
# Metal GPU via llama.cpp / Ollama
# vLLM/SGLang not available on macOS
```

### 5.3 Windows
```powershell
.\launch-windows.ps1
# Or manual:
py -3.11 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup.py
python -m uvicorn app:app --host 127.0.0.1 --port 7000
```

---

## 6. Production/Private Deployment

```
Recommended Architecture:

                         INTERNET
                            │
                            ▼
              ┌─────────────────────────┐
              │  Reverse Proxy / Gateway │
              │  (nginx/Caddy/Traefik   │
              │   + Cloudflare Access   │
              │   or Tailscale)         │
              │                         │
              │  HTTPS termination      │
              │  Authentication         │
              │  Rate limiting          │
              └───────────┬─────────────┘
                          │ (HTTPS)
                          ▼
              ┌─────────────────────────┐
              │  Odysseus :7000          │
              │  127.0.0.1 only         │
              │  AUTH_ENABLED=true      │
              │  SECURE_COOKIES=true    │
              │  LOCALHOST_BYPASS=false │
              └─────────────────────────┘
```

Key settings for production:
- `AUTH_ENABLED=true` (required)
- `LOCALHOST_BYPASS=false` (required)
- `SECURE_COOKIES=true` (required for HTTPS)
- `APP_BIND=127.0.0.1` (keep internal)
- Reverse proxy handles HTTPS

---

## 7. Network Architecture

```
Internal Network (Docker bridge):

  odysseus:7000 ──────┐
  chromadb:8000 ──────┤
  searxng:8080  ──────┤── odysseus-network (internal)
  ntfy:8091     ──────┘

Host access:
  • host.docker.internal → Docker host (for Ollama on host)
  • Ollama: http://host.docker.internal:11434/v1

External access (if configured):
  • APP_BIND:APP_PORT → host:7000
  • Should go through reverse proxy
```

---

## 8. Cookbook Model Serving Architecture

```
Model download and serving flow:

1. Cookbook scans hardware (GPU, VRAM, RAM)
2. Recommends models that fit (fit scoring)
3. User selects model → background download via tmux
4. Storage: ./data/huggingface (persisted)
5. Serve: vLLM / llama.cpp / SGLang via tmux
   └─ Served on localhost:8000-8020
6. Odysseus auto-discovers served models
7. Endpoint added to model list automatically

Remote servers:
  1. Generate SSH key in Cookbook → Settings → Servers
  2. Add public key to remote server's authorized_keys
  3. Odysseus can manage remote GPU servers
```

---

## 9. Service Health & Monitoring

```
Health endpoints:
  • /api/companion/ping → {ok, name, version}
  • Database connectivity via SessionLocal
  • ChromaDB heartbeat via MemoryVectorStore.healthy

Keep-alive:
  • 60s endpoint ping loop
  • Dead-host detection (2 failures → 20s cooldown)

Logging:
  • Structured logging (timestamp, name, level, message)
  • X-Request-Id for request tracing
  • Slow request logging (>=500ms)
  • Error logging with stack traces

Startup checks:
  • ChromaDB connection (graceful degradation if unavailable)
  • MCP server connections (20s timeout, async)
  • Embedding model pre-warming
  • LLM endpoint connectivity
```

---

## 10. Backup & Restore

All persistent data in `data/` directory:
```
Backup:
  tar -czf odysseus-backup.tar.gz data/

Restore:
  tar -xzf odysseus-backup.tar.gz

Critical files:
  • data/app.db          (all sessions, messages, documents)
  • data/auth.json       (user accounts)
  • data/memory.json     (persistent memories)
  • data/settings.json   (app configuration)
  • data/chroma/         (vector embeddings — large)
```

Backup API available at `/api/backup` (admin only).
