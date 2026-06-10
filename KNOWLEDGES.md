# Odysseus Knowledge Base

> **Comprehensive technical knowledge about the Odysseus codebase.**
> Last updated: 2026-06-10

---

## 1. Project Identity

**Odysseus** is a self-hosted AI workspace — a local-first, privacy-first alternative to ChatGPT and Claude UI. It runs on your own hardware with your own data. The project is MIT-licensed and written in **Python 3.11+** (backend) and **vanilla JavaScript ES modules** (frontend), with no bundler/build step.

- **Repository**: `pewdiepie-archdaemon/odysseus`
- **Entry Point**: `app.py` (FastAPI orchestrator)
- **Version**: `1.0.0` (app), `0.9.1` (core constants)

---

## 2. Core Principles

1. **Local-first, privacy-first** — All data in `data/` (gitignored). No telemetry, no cloud dependency.
2. **Self-hosted** — Docker Compose with ChromaDB, SearXNG, ntfy. Everything runs locally.
3. **Multi-model** — vLLM, llama.cpp, Ollama, OpenRouter, OpenAI, Anthropic all supported via unified API adapters.
4. **Agent-driven** — Built on [opencode](https://github.com/anomalyco/opencode); MCP, web, files, shell, skills, memory tools.
5. **No build step** — Frontend ships raw ES modules. Backend is plain Python. Simpler dev loop.
6. **Multi-user with privilege model** — Per-user boolean flags, message limits, model allowlists.
7. **Graceful degradation** — ChromaDB offline? Fall back to BM25-only memory. GPU missing? Use CPU/API.

---

## 3. Technology Stack

| Layer | Technology |
|-------|-----------|
| **Web Framework** | FastAPI (Python) + Uvicorn |
| **Database ORM** | SQLAlchemy 2.0 (SQLite default, PostgreSQL-compatible) |
| **Vector Store** | ChromaDB (via `chromadb-client`) |
| **Embeddings** | fastembed (ONNX, `all-MiniLM-L6-v2` default) |
| **Auth** | bcrypt + session tokens + TOTP 2FA |
| **Frontend** | Vanilla JS ES modules, no bundler |
| **PWA** | Service Worker (`sw.js`) + manifest.json |
| **MCP** | Model Context Protocol (stdio + SSE transports) |
| **Search** | SearXNG, Brave, Google, Tavily, Serper |
| **Container** | Docker, docker-compose, gosu (privilege dropping) |
| **Model Serving** | vLLM, llama.cpp, SGLang, Ollama, Diffusers |
| **Scheduling** | asyncio tasks + APScheduler-like cron |
| **Email** | IMAP/SMTP via `imaplib`/`smtplib` + CalDAV-aware |
| **Calendar** | CalDAV via `caldav` library |
| **TTS/STT** | Provider-pluggable (OpenAI TTS, Whisper, etc.) |

---

## 4. Directory Structure

```
odysseus/
├── app.py                      # FastAPI entry point, middleware, route registration
├── setup.py                    # First-time setup (dirs, DB, admin user)
├── Dockerfile                  # python:3.12-slim, gosu, system deps
├── docker-compose.yml          # Multi-service: Odysseus + ChromaDB + SearXNG + ntfy
│
├── core/                       # Core infrastructure (no business logic)
│   ├── auth.py                 # AuthManager: multi-user, bcrypt, sessions, 2FA
│   ├── database.py             # SQLAlchemy models, EncryptedText, TimestampMixin
│   ├── middleware.py            # SecurityHeaders, RequestId, require_admin decorator
│   ├── models.py               # Pure data models (Session, ChatMessage dataclasses)
│   ├── session_manager.py      # Session CRUD, lazy message hydration
│   ├── constants.py            # App-wide constants (paths, defaults)
│   ├── exceptions.py           # Custom exceptions (SessionNotFound, LLMServiceError, etc.)
│   ├── feature_flags.py        # Feature flag system (file + env var overrides)
│   ├── atomic_io.py            # Atomic JSON file writes
│   ├── response_types.py       # Standardized API response envelope (ok/err)
│   └── platform_compat.py      # Platform compatibility utilities
│
├── src/                        # Business logic & services (~75 files)
│   ├── agent_loop.py           # Streaming agent: multi-round tool execution
│   ├── agent_tools.py          # Tool definitions, parsing, execution dispatch
│   ├── tool_execution.py       # Tool dispatcher: path confinement, result formatting
│   ├── tool_parsing.py         # Regex-based tool block parsing (fenced, XML, DSML)
│   ├── tool_implementations.py # Native tool implementations
│   ├── tool_schemas.py         # Tool input/output schemas
│   ├── tool_security.py        # Tool access control, blocked tools
│   ├── tool_index.py           # Embedding-based tool indexing for RAG
│   ├── chat_processor.py       # Hybrid BM25+vector memory retrieval
│   ├── chat_handler.py         # Unified chat processing pipeline
│   ├── llm_core.py             # LLM API adapters, caching, dead-host cooldown
│   ├── mcp_manager.py          # MCP server lifecycle and tool dispatch
│   ├── app_initializer.py      # Dependency injection, component graph
│   ├── memory.py               # Persistent memory CRUD (MemoryManager)
│   ├── memory_vector.py        # ChromaDB vector memory store
│   ├── personal_docs.py        # Personal document indexing (RAG)
│   ├── rag_manager.py          # RAG manager (ChromaDB document search)
│   ├── rag_singleton.py        # Singleton RAG manager instance
│   ├── rag_vector.py           # Vector operations for RAG
│   ├── embeddings.py           # Fastembed ONNX embedding models
│   ├── model_discovery.py      # Local + API endpoint enumeration
│   ├── model_context.py        # Context length estimation
│   ├── context_budget.py       # Token budget management
│   ├── context_compactor.py    # Context window compaction
│   ├── research_handler.py     # Deep research job management
│   ├── deep_research.py        # Multi-step research pipeline
│   ├── task_scheduler.py       # Cron-based scheduled task execution
│   ├── task_endpoint.py        # Task API endpoints
│   ├── webhook_manager.py      # Outgoing webhook notifications
│   ├── preset_manager.py       # Chat preset CRUD
│   ├── api_key_manager.py      # API key storage
│   ├── settings.py             # Application settings management
│   ├── settings_scrub.py       # Secrets scrubbing for logs/exports
│   ├── secret_storage.py       # Fernet encryption for DB columns
│   ├── prompt_security.py      # Prompt injection gates, untrusted context policy
│   ├── url_safety.py           # URL validation and safety checks
│   ├── rate_limiter.py         # Rate limiting utilities
│   ├── auth_helpers.py         # Auth helper functions
│   ├── event_bus.py            # Internal event bus
│   ├── readiness.py            # Readiness probe support
│   ├── cleanup_service.py      # Orphaned resource cleanup
│   ├── builtin_actions.py      # Built-in agent actions
│   ├── builtin_mcp.py          # Built-in MCP server registration
│   ├── bg_jobs.py              # Background job runner
│   ├── bg_monitor.py           # Background job monitoring
│   ├── config.py               # Configuration management
│   ├── integrations.py         # External integrations
│   ├── caldav_sync.py          # CalDAV sync logic
│   ├── caldav_writeback.py     # CalDAV writeback
│   ├── search/                 # Search service implementations
│   ├── cache/                  # Caching utilities
│   ├── upload_handler.py       # File upload handling
│   ├── document_processor.py   # Document processing
│   └── ...                     # 40+ more modules
│
├── routes/                     # API route handlers (~40 files)
│   ├── chat_routes.py          # /api/chat, /api/chat_stream
│   ├── session_routes.py       # /api/sessions
│   ├── auth_routes.py          # /api/auth (login, signup, user mgmt)
│   ├── memory_routes.py        # /api/memory
│   ├── skills_routes.py        # /api/skills
│   ├── document_routes.py      # /api/documents
│   ├── research_routes.py      # /api/research
│   ├── email_routes.py         # /api/email
│   ├── calendar_routes.py      # /api/calendar
│   ├── shell_routes.py         # /api/shell
│   ├── model_routes.py         # /api/models
│   ├── cookbook_routes.py      # /api/cookbook
│   ├── mcp_routes.py           # /api/mcp
│   ├── task_routes.py          # /api/tasks
│   ├── webhook_routes.py       # /api/webhooks
│   ├── api_token_routes.py     # /api/tokens
│   ├── preset_routes.py        # /api/presets
│   ├── gallery_routes.py       # /api/gallery
│   ├── note_routes.py          # /api/notes
│   ├── settings_routes.py      # /api/settings
│   ├── search_routes.py        # /api/search
│   ├── compare_routes.py       # /api/compare
│   └── ...                     # 20+ more route modules
│
├── services/                   # Service layer implementations
│   ├── memory/                 # Memory service (BM25 + vector)
│   ├── docs/                   # Document service
│   ├── search/                 # Web search service
│   ├── research/               # Deep research service
│   ├── shell/                  # Shell execution service
│   ├── tts/                    # Text-to-speech service
│   ├── stt/                    # Speech-to-text service
│   ├── hwfit/                  # Hardware fitness (Cookbook)
│   ├── youtube/                # YouTube transcript service
│   ├── faces/                  # Face detection service
│   └── cache/                  # Cache service
│
├── mcp_servers/                # Built-in MCP tool servers
│   ├── _common.py              # Shared constants and helpers
│   ├── email_server.py         # IMAP/SMTP email tools
│   ├── memory_server.py        # RAM knowledge store tools
│   ├── rag_server.py           # Document retrieval tools
│   └── image_gen_server.py     # Image generation tools
│
├── companion/                  # LAN pairing system
│   ├── __init__.py
│   ├── pairing.py              # Token minting, QR generation
│   └── routes.py               # /api/companion/* endpoints
│
├── scripts/                    # CLI subcommands (~20)
│   ├── odysseus                # Dispatcher entry point
│   ├── _lib/cli.py             # Shared CLI library
│   ├── odysseus-mcp            # MCP management CLI
│   ├── odysseus-mail           # Email CLI
│   ├── odysseus-memory         # Memory CLI
│   └── ...                     # 17 more subcommands
│
├── static/                     # Frontend (ES modules, no build)
│   ├── index.html              # Main SPA
│   ├── login.html              # Auth UI
│   ├── landing.html            # Marketing landing
│   ├── app.js                  # Main app bundle (ES modules)
│   ├── style.css               # Global styles
│   ├── sw.js                   # Service Worker (PWA)
│   ├── manifest.json           # PWA manifest
│   ├── js/                     # 70+ JS modules
│   │   ├── chat.js             # Chat submission, SSE streaming
│   │   ├── chatRenderer.js     # Message rendering, code blocks
│   │   ├── chatStream.js       # SSE parsing, chunk handling
│   │   ├── sessions.js         # Session management
│   │   ├── theme.js            # 12+ themes, color picker
│   │   ├── models.js           # Model discovery, provider selection
│   │   ├── memory.js           # Memory UI management
│   │   ├── markdown.js         # Markdown → HTML rendering
│   │   ├── ui.js               # Toast, clipboard, scroll utilities
│   │   ├── init.js             # Auth check, privilege gating
│   │   ├── settings.js         # Settings UI
│   │   ├── storage.js          # Safe localStorage API
│   │   ├── fileHandler.js      # File upload, attachment preview
│   │   ├── editor/             # Rich document editor (40+ files)
│   │   ├── compare/            # A/B model comparison
│   │   ├── research/           # Deep research UI
│   │   ├── calendar/           # Calendar UI
│   │   ├── color/              # Color picker utilities
│   │   ├── markdown/           # Markdown processing
│   │   ├── util/               # General utilities
│   │   └── MODULE_SUMMARY.md   # Frontend module documentation
│   └── lib/                    # 3rd-party deps (cached locally)
│
├── tests/                      # Test suite (~250 files)
├── data/                       # User data (gitignored, mounted as volume)
├── logs/                       # Application logs (gitignored)
├── docs/                       # Documentation and landing page
├── docker/                     # Docker support files
│   ├── entrypoint.sh           # Privilege-dropping entrypoint
│   ├── gpu.nvidia.yml          # NVIDIA GPU overlay
│   └── gpu.amd.yml             # AMD GPU overlay
└── config/                     # Configuration files
    └── searxng/                # SearXNG configuration
```

---

## 5. Database Models

All models are SQLAlchemy 2.0 declarative with `TimestampMixin` (auto `created_at`/`updated_at`).

| Model | Table | Purpose |
|-------|-------|---------|
| `Session` | `sessions` | Chat sessions with metadata, owner, folder, RAG flag |
| `ChatMessage` | `chat_messages` | Messages with multimodal content, role, pinned flag |
| `Document` | `documents` | Artifact/canvas editor documents |
| `Note` | `notes` | Google Keep-style notes with categories, due dates |
| `ModelEndpoint` | `model_endpoints` | LLM provider endpoints (base_url, API key, model cache) |
| `ScheduledTask` | `scheduled_tasks` | Recurring AI tasks with cron expressions |
| `GalleryImage` | `gallery_images` | Generated image library with albums |
| `ApiToken` | `api_tokens` | Bearer tokens (prefix-hashed, scoped) |
| `McpServer` | `mcp_servers` | MCP server registry (enabled/disabled, tool filtering) |
| `CalendarEvent` | `calendar_events` | Calendar events (CalDAV-synced) |
| `CalendarCal` | `calendar_cals` | Calendar definitions (colors, sync URL) |
| `EmailAccount` | `email_accounts` | IMAP/SMTP account configurations |
| `Contact` | `contacts` | Address book contacts |
| `UserPrefs` | `user_prefs` | Per-user UI preferences |
| `WebhookEndpoint` | `webhook_endpoints` | Outgoing webhook configurations |
| `Skill` | `skills` | Agent skill definitions |

**Special Column Types**:
- `EncryptedText`: Fernet-encrypted at rest, transparently decrypted on read
- `TimestampMixin`: Automatic `created_at`/`updated_at` on all models

---

## 6. Key Architecture Decisions

### 6.1 Lazy Message Hydration
Session metadata loads at boot. Messages are fetched from DB on demand. Prevents RAM blow-up with thousands of sessions — only the 100 most recent sessions' metadata stays in memory.

### 6.2 Prefix-Based API Token Cache
API tokens are validated with O(1) prefix lookup instead of O(n) bcrypt. Token prefix (`ody_<prefix><hash>`) — the prefix maps to the full hash in an in-memory dict. Invalidated on token create/revoke.

### 6.3 Dead-Host Cooldown with Grace
Two consecutive failures trigger a 20s cooldown for a host. Single transient blips don't lock out. Any success resets the counter immediately.

### 6.4 Hybrid BM25 + Vector Memory
Keyword retrieval (BM25) works offline. Vector search (ChromaDB) fills gaps when available. Category-aware boosting for identity/contact/preference queries. Resistant to ChromaDB downtime.

### 6.5 No Bundler / Raw ES Modules
Simpler dev loop, no build cache issues. Larger JS payload mitigated by HTTP/2 multiplexing + gzip + cache-revalidation via Service Worker.

### 6.6 In-Process Tool Execution
Agent tools run in-process (not separate microservices). Simpler deployment, faster tool calls. Mitigated by uvicorn multi-worker + 60s tool timeouts + 10K char output limits.

### 6.7 In-Process Pollers & Schedulers
Email polling and task scheduling run as asyncio tasks inside the app process. Configurable via `ODYSSEUS_INPROCESS_POLLERS` and `ODYSSEUS_INPROCESS_TASKS` env vars.

---

## 7. Agent Tool System

The agent uses **fenced code blocks** to invoke tools. The LLM writes:

    ```bash
    echo "hello"
    ```

And the tool execution layer parses, validates, and runs it.

### Supported Tool Tags

| Tag | Purpose | Admin Only |
|-----|---------|------------|
| `bash` | Shell commands | Yes |
| `python` | Python execution | Yes |
| `web_search` | Web search | No |
| `create_document` | Create new artifact | No |
| `edit_document` | FIND/REPLACE edit | No |
| `update_document` | Full document replacement | No |
| `read_file` | Read file content (path-confined) | Yes |
| `write_file` | Write file content (path-confined) | Yes |
| `manage_memory` | CRUD persistent memory | No |
| `manage_notes` | CRUD notes/todos | No |
| `manage_tasks` | CRUD scheduled tasks | No |
| `manage_calendar` | CRUD calendar events | No |
| `list_emails` | List inbox messages | No |
| `read_email` | Read email content | No |
| `send_email` | Send email | No |
| `bulk_email` | Bulk email actions | No |
| `generate_image` | AI image generation | No |

### Tool Execution Flow
1. LLM writes fenced code block with tool tag
2. `parse_tool_blocks()` regex-extracts blocks
3. `execute_tool_block()` dispatches to MCP or native implementation
4. Results injected back into LLM context
5. Loop continues until max rounds (10) or agent signals DONE/BLOCKED

### Security Constraints
- **Path confinement**: `read_file`/`write_file` restricted to `data/`, `/tmp`, `$TMPDIR`
- **Sensitive path blocking**: `.ssh`, `.gnupg`, `.env`, shell rc files blocked
- **Output limits**: 10K chars per tool, 60s timeout per tool
- **Prompt injection gates**: `UNTRUSTED_CONTEXT_POLICY` wraps user content
- **Owner-scoped access**: Tool results filtered by user identity

---

## 8. Authentication & Authorization

### Auth Flow
1. **First-run**: `POST /api/auth/setup` creates admin account (rate-limited: 3 req/5min)
2. **Login**: `POST /api/auth/login` validates bcrypt password, sets `odysseus_session` cookie
3. **Cookie Auth**: `AuthMiddleware` extracts cookie, validates session token
4. **Bearer Token**: `Authorization: Bearer ody_<prefix><hash>` for API access
5. **Localhost Bypass**: `LOCALHOST_BYPASS=true` skips auth for loopback (dev only)
6. **Internal Tool Bypass**: `X-Odysseus-Internal-Token` header for agent loopback calls

### Privilege Model
Per-user boolean flags: `can_use_agent`, `can_use_bash`, `can_use_documents`, `can_generate_images`, `can_manage_memory`, `can_use_research`, `can_use_browser`, plus integer limits (`max_messages_per_day`) and model allowlists (`allowed_models`). Admins get all privileges.

### Reserved Usernames
`internal-tool`, `api`, `demo`, `system` — blocked from registration to prevent impersonation of synthetic owner sentinels.

---

## 9. Frontend Architecture

### Module Organization (70+ ES modules)
- **Chat**: `chat.js`, `chatRenderer.js`, `chatStream.js` — SSE streaming, message rendering
- **Sessions**: `sessions.js` — Create, load, switch, fork, archive
- **Theme**: `theme.js` — 12+ themes, zero-flash application, dynamic favicon
- **Models**: `models.js`, `modelPicker.js`, `modelSort.js` — Endpoint discovery, provider selection
- **Editor**: `editor/` (40+ files) — Rich document canvas editor
- **Memory**: `memory.js`, `rag.js` — Memory management UI
- **Research**: `research/` — Deep research visualization
- **Compare**: `compare/` — A/B blind model comparison
- **Calendar**: `calendar/`, `calendar.js` — Calendar views
- **Email**: `emailInbox.js`, `emailLibrary/` — IMAP inbox UI
- **Settings**: `settings.js`, `admin.js` — App configuration

### PWA Architecture
- Service Worker (`sw.js`): stale-while-revalidate for HTML, network-first for JS/CSS, cache-first for assets
- `manifest.json`: Standalone display, route-specific manifests for /calendar, /notes, /email

---

## 10. MCP (Model Context Protocol) System

### Architecture
- `McpManager` singleton manages all MCP server connections
- Supports **stdio** (subprocess) and **SSE** (HTTP) transports
- Tool names qualified as `mcp__<server_id>__<tool_name>`
- DB config via `McpServer` model

### Built-in Servers
| Server | Transport | Tools |
|--------|-----------|-------|
| `email_server.py` | stdio | IMAP/SMTP email (read, send, list, search, manage folders) |
| `memory_server.py` | stdio | Memory CRUD (list, add, edit, delete, search) |
| `rag_server.py` | stdio | Document retrieval (query, search chunks) |
| `image_gen_server.py` | stdio | Image generation |
| `@playwright/mcp` | npx stdio | Browser automation (page nav, screenshots, vision) |

---

## 11. Deployment Modes

### Docker (Recommended)
- `docker compose up -d --build`
- Multi-container: Odysseus + ChromaDB + SearXNG + ntfy
- Port `7000` (configurable via `APP_PORT`)
- Binds to `127.0.0.1` by default
- GPU overlays: `docker/gpu.nvidia.yml`, `docker/gpu.amd.yml`
- Privilege dropping via `gosu` (PUID/PGID)

### Native Linux/macOS
- `python3 -m venv venv && pip install -r requirements.txt`
- `python setup.py && uvicorn app:app --host 127.0.0.1 --port 7000`
- macOS: `./start-macos.sh` (port 7860, Metal GPU)

### Native Windows
- `.\launch-windows.ps1` or manual venv + pip install
- Ollama recommended for local models on Windows

---

## 12. Testing Strategy

- **Framework**: pytest with async support
- **Coverage**: ~250 test files
- **Categories**: auth/security, agent/tool execution, chat/streaming, database/schema, search, email, memory retrieval, tool confinement, MCP dispatch

---

## 13. Common Operations Reference

| Task | File/Command |
|------|-------------|
| Add a new route | Create file in `routes/`, add `setup_*_routes()` function, register in `app.py` |
| Add a new tool | Add to `src/agent_tools.py` or create MCP server in `mcp_servers/` |
| Add a DB model | Add to `core/database.py`, run migration (auto on startup) |
| Add a feature flag | Add to `_FEATURES` list in `core/feature_flags.py` |
| Add a theme | Add to `THEMES` object in `static/js/theme.js` |
| Add a frontend module | Create in `static/js/`, import in `app.js` |
| Add a CLI command | Create `scripts/odysseus-<name>`, it auto-discovers |
| Debug agent tool calls | Check agent loop logs, `MAX_AGENT_ROUNDS=10`, tool output limits |
| Check memory retrieval | Look at `chat_processor._hybrid_retrieve()`, BM25 + vector scores |
