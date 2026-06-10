# Backend Architecture

> **Detailed architecture of the Odysseus Python backend.**

---

## 1. Application Entry Point (`app.py`)

The `app.py` file is a **slim orchestrator** — it wires everything together but contains minimal business logic.

### Startup Sequence
```
1. register_static_mime_types()     # Force JS/MJS MIME types (Windows compat)
2. load_dotenv(encoding="utf-8-sig") # Load .env (UTF-8 BOM tolerant)
3. Create FastAPI app instance
4. Add RequestIdMiddleware          # Outermost: X-Request-Id tracing
5. Add CORS middleware               # Origin validation
6. Add SecurityHeadersMiddleware     # CSP, X-Frame, Referrer-Policy
7. Initialize DB (create_all)
8. Initialize AuthManager            # Load auth.json + sessions.json
9. Add RequestTimeoutMiddleware      # 45s hard timeout
10. Add AuthMiddleware               # Cookie + Bearer token validation
11. Initialize Managers (app_initializer)
12. Register Routes (40+ modules, feature-flag gated)
13. Mount Static Files
14. Startup Event:
    - Purge incognito sessions
    - Initialize services (RAG, TTS, STT, MCP, TaskScheduler)
    - Start keep-alive loop
15. Global Exception Handlers
```

---

## 2. Core Layer (`core/`)

### 2.1 Database (`core/database.py`)
- **SQLAlchemy 2.0** declarative base
- **SQLite** by default, PostgreSQL-compatible (`DATABASE_URL` env var)
- **Engine event listener** for `PRAGMA foreign_keys=ON` (SQLite)
- **`TimestampMixin`**: auto `created_at`/`updated_at` on all models
- **`EncryptedText`**: TypeDecorator for Fernet-encrypted columns at rest
- **`SessionLocal`**: Thread-safe session factory

**Model Relationships**:
```
Session (1) ──────────── (N) ChatMessage
Session (1) ──────────── (N) Document
CalendarCal (1) ──────── (N) CalendarEvent
EmailAccount            (standalone)
ApiToken                (standalone)
McpServer               (standalone)
```

### 2.2 Authentication (`core/auth.py`)
```
AuthManager
├── _config: auth.json (users, passwords, privileges, 2FA)
├── _sessions: sessions.json (token → {username, expiry})
├── _sessions_lock: threading.RLock (concurrent mutation safety)
├── _setup_lock: threading.Lock (first-run setup serialization)
│
├── Methods:
│   ├── is_configured() → bool
│   ├── create_admin(password) → username
│   ├── authenticate(username, password) → token | None
│   ├── validate_token(token) → username | None
│   ├── create_user(username, password, is_admin, privileges)
│   ├── update_user(username, updates)
│   ├── delete_user(username)
│   ├── list_users() → [{username, is_admin, privileges, ...}]
│   ├── change_password(username, old, new) → bool
│   ├── setup_totp(username) → (secret, qr_uri)
│   ├── enable_totp(username, code) → bool
│   └── revoke_token(token)
│
└── Reserved usernames: internal-tool, api, demo, system
```

**Password Hashing**: bcrypt with auto-generated salts
**Session Token TTL**: 7 days
**2FA**: TOTP via `pyotp`

### 2.3 Middleware (`core/middleware.py`)

```
RequestIdMiddleware
├── Reads X-Request-Id from client (for distributed tracing)
├── Generates short UUID if not provided
├── Logs: method, path, status, duration at response time
└── Adds X-Request-Id to response header

SecurityHeadersMiddleware
├── X-Content-Type-Options: nosniff
├── Referrer-Policy: no-referrer
├── X-Frame-Options: DENY (except tool iframes)
└── CSP with per-request nonce (for inline scripts)

require_admin(request) decorator
├── Checks X-Odysseus-Internal-Token header
├── Checks request.state.current_user == "internal-tool"
├── Checks auth_manager.is_admin(current_user)
└── Raises 403 if none pass
```

### 2.4 Session Manager (`core/session_manager.py`)
```
SessionManager
├── load_sessions()          # Load top 100 non-archived sessions (metadata only)
├── create_session(id, name, url, model, owner) → Session
├── get_session(id)          # Hydrate full session with messages from DB
├── add_message(session_id, ChatMessage)
├── archive_session(id)      # Soft-delete
├── delete_session(id)       # Hard-delete
└── _db_to_session_meta()    # DB row → Session dataclass
```

**Lazy Hydration Strategy**:
- Boot: Load only session metadata (id, name, model, last_accessed) — top 100
- On read: Fetch messages from `chat_messages` table for that session
- Prevents RAM blow-up from thousands of sessions

---

## 3. Business Logic Layer (`src/`)

### 3.1 LLM Core (`src/llm_core.py`)

**API Adapters**:
```
Native Anthropic API   ←→  /v1/messages (with native tool calling)
OpenAI-compatible      ←→  /v1/chat/completions (vLLM, Ollama, OpenRouter, LM Studio)
Fallback Chain         ←→  Try endpoint 1, fallback to endpoint 2
```

**Key Features**:
- **Response Caching**: SHA256-keyed, LRU eviction (128 entries)
- **Dead-Host Cooldown**: 2 consecutive failures → 20s cooldown
- **Host Health Tracking**: Thread-safe maps with lock
- **Model Activity**: Records last-used timestamps
- **Shared AsyncClient**: Connection pooling, HTTP/2 disabled (streaming issues)

**Functions**:
```
llm_call(url, model, messages, temp, max_tokens) → str
llm_call_async(url, model, messages, temp, max_tokens) → str
stream_llm(url, model, messages, ...) → AsyncGenerator[str]
stream_llm_with_fallback(urls, model, messages, ...) → AsyncGenerator[str]
```

### 3.2 Agent Loop (`src/agent_loop.py`)

```
run_agent(session_id, messages, model, endpoint, owner, ...)
│
├── 1. Build system prompt (_AGENT_PREAMBLE + _AGENT_RULES)
├── 2. Inject available tool schemas
├── 3. Load MCP disabled-tool map from DB
├── 4. Call stream_llm() with full context
│
├── 5. Parse response for tool invocations
│     ├── Fenced code blocks: ```tool_name ... ```
│     ├── XML syntax: <invoke name="tool"><parameter>...</parameter></invoke>
│     └── [TOOL_CALL] ... [/TOOL_CALL] blocks
│
├── 6. Execute tool via execute_tool_block()
│     ├── Blocked tool check (per-owner)
│     ├── MCP dispatch (mcp__<server>__<tool>)
│     ├── Native implementation dispatch
│     └── Format result (truncate to 10K chars)
│
├── 7. Inject tool result back into context
├── 8. Loop until MAX_AGENT_ROUNDS (10) or agent signals DONE/BLOCKED
└── 9. Return final response + tool call history
```

**Agent Rules** (injected as system prompt):
- BIAS TOWARD ACTION on edit requests
- After tool success: ONE short sentence confirmation
- After tool failure: Retry with fix or explain blocking
- Declare DONE only when task is complete
- Calendar: list calendars FIRST before operations
- Bulk email: use `bulk_email` once, never loop
- Identity facts → `manage_memory`, not `manage_contact`

### 3.3 Tool Execution (`src/tool_execution.py`)

**Path Confinement**:
```
Allowed roots: data/, /tmp, /private/tmp, $TMPDIR
Blocked paths: .ssh, .gnupg, .env, shell rc files, SSH keys
Blocked filenames: authorized_keys, id_rsa, id_ed25519, known_hosts
Extra roots: configurable via tool_path_extra_roots setting
```

**Tool Execution Flow**:
```
execute_tool_block(block, owner, session_id)
│
├── Check blocked tools (per-owner)
├── Check admin-gated tools (bash, python, read_file, write_file)
├── Dispatch:
│     ├── MCP tools → mcp_manager.call_tool()
│     ├── shell → ShellService.execute()
│     ├── python → subprocess python -c
│     ├── web_search → SearchService.search()
│     ├── read_file/write_file → path-confined I/O
│     ├── create_document/edit_document → document_processor
│     ├── manage_memory → memory_manager
│     ├── list_emails/read_email/send_email → email_service
│     └── manage_calendar → calendar_service
│
├── Apply limits:
│     ├── 10,000 char output max
│     ├── 60s timeout per tool
│     └── 20,000 char read max
│
└── Return formatted result string
```

### 3.4 Memory & RAG

**Hybrid Retrieval** (`src/chat_processor.py`):
```
_hybrid_retrieve(message, mem_entries, k=5) → top-k memories
│
├── BM25 Keyword Scoring
│     ├── IDF from memory corpus
│     ├── Binary TF (memory entries are short)
│     └── Length normalization (k1=1.5, b=0.75)
│
├── Vector Similarity (if ChromaDB healthy)
│     └── Cosine similarity via MemoryVectorStore
│
├── Category-Aware Boost
│     ├── Identity queries: 1.4x boost
│     ├── Contact queries: 1.3x boost
│     └── Preference queries: 1.2x boost
│
├── Recency Tiebreaker: Max 5% contribution
├── Threshold Gate: Score must exceed minimum
└── Max 5 memories returned
```

**MemoryVectorStore** (`src/memory_vector.py`):
- Backed by ChromaDB collection
- Uses fastembed (ONNX) for embeddings
- Automatically rebuilds index from existing memories if empty
- Gracefully degrades if ChromaDB unavailable

**RAG Manager** (`src/rag_manager.py`):
- Separate ChromaDB collection for personal documents
- Document chunking + embedding on upload
- Similarity threshold: 0.35

### 3.5 MCP Manager (`src/mcp_manager.py`)

```
McpManager (singleton)
├── _connections: {server_id → {status, name, error}}
├── _tools: {server_id → [tool_schemas]}
├── _sessions: {server_id → ClientSession}
├── _stacks: {server_id → AsyncExitStack}
├── _generation: int (incremented on connect/disconnect)
│
├── connect_server(id, name, transport, command, args, env, url) → bool
│     ├── stdio: spawn subprocess, connect via stdio
│     └── sse: connect via HTTP SSE
│
├── disconnect_server(id)
├── call_tool(server_id, tool_name, arguments) → [TextContent]
├── list_tools() → [tool_schemas]
├── disconnect_all()
└── _format_mcp_connection_error() → user-friendly error messages
```

### 3.6 Scheduled Tasks (`src/task_scheduler.py`)

```
TaskScheduler
├── Shared TTL cache (singleflight pattern)
├── cron expression parser (via croniter)
├── Timezone-aware scheduling (ZoneInfo)
├── Computes next_run from: schedule, time, day, date, cron, tz
│
├── Schedule types:
│     ├── "once": Run once at scheduled_time
│     ├── "daily": Run every day at scheduled_time
│     ├── "weekly": Run on scheduled_day at scheduled_time
│     ├── "monthly": Run on scheduled_date at scheduled_time
│     └── "cron": Cron expression (via croniter)
│
└── Execution: Agent loop with task prompt, result saved to DB
```

---

## 4. Route Layer (`routes/`)

### Standard Route Pattern
```python
# routes/example_routes.py
from fastapi import APIRouter, Request

def setup_example_routes(router: APIRouter, deps: dict):
    chat_handler = deps["chat_handler"]
    memory_manager = deps["memory_manager"]

    @router.post("/api/example")
    async def example_endpoint(request: Request):
        current_user = get_current_user(request)
        # ... business logic ...
        return {"ok": True}
```

### Route Registration in `app.py`
```python
from routes.chat_routes import setup_chat_routes
# 40+ imports...

deps = { "chat_handler": ..., "memory_manager": ..., ... }

if features.email:
    setup_email_routes(app, deps)
if features.calendar:
    setup_calendar_routes(app, deps)
# ... feature-flag gated registration ...
```

### Key Route Modules

| Module | Base Path | Key Endpoints |
|--------|-----------|---------------|
| `chat_routes.py` | `/api/chat` | POST `/chat`, GET `/chat_stream` |
| `session_routes.py` | `/api/sessions` | CRUD for chat sessions |
| `auth_routes.py` | `/api/auth` | Login, signup, user mgmt, 2FA |
| `memory_routes.py` | `/api/memory` | Memory CRUD, search |
| `document_routes.py` | `/api/documents` | Document editor CRUD |
| `email_routes.py` | `/api/email` | IMAP mailbox, send, bulk |
| `calendar_routes.py` | `/api/calendar` | CalDAV sync, event CRUD |
| `shell_routes.py` | `/api/shell` | Command execution |
| `model_routes.py` | `/api/models` | Endpoint discovery, model list |
| `cookbook_routes.py` | `/api/cookbook` | Model download, serve |
| `mcp_routes.py` | `/api/mcp` | MCP server management |
| `research_routes.py` | `/api/research` | Deep research jobs |
| `skills_routes.py` | `/api/skills` | Agent skill management |
| `task_routes.py` | `/api/tasks` | Scheduled task CRUD |
| `webhook_routes.py` | `/api/webhooks` | Webhook management |
| `api_token_routes.py` | `/api/tokens` | API token CRUD |
| `preset_routes.py` | `/api/presets` | Chat preset CRUD |
| `gallery_routes.py` | `/api/gallery` | Generated image library |
| `note_routes.py` | `/api/notes` | Notes/todos CRUD |
| `search_routes.py` | `/api/search` | Web search |
| `compare_routes.py` | `/api/compare` | Model comparison |
| `settings_routes.py` | `/api/settings` | App settings |
| `companion_routes.py` | `/api/companion` | LAN pairing |

---

## 5. Service Layer (`services/`)

Each service encapsulates a capability with a clean async interface:

```
services/
├── memory/      → MemoryService      (BM25 + vector memory operations)
├── docs/        → DocsService        (Document indexing and RAG)
├── search/      → SearchService      (SearXNG, Brave, Google, Tavily, Serper)
├── research/    → ResearchService    (Multi-step web research + synthesis)
├── shell/       → ShellService       (Sandboxed command execution)
├── tts/         → TTSService         (Text-to-speech provider abstraction)
├── stt/         → STTService         (Speech-to-text provider abstraction)
├── hwfit/       → HardwareFitService (GPU/VRAM detection, model fit scoring)
├── youtube/     → YouTubeService     (YouTube transcript extraction)
├── faces/       → FaceService        (Face detection)
└── cache/       → CacheService       (Shared caching layer)
```

---

## 6. Feature Flags System

Located in `core/feature_flags.py`, the system gates backend routes AND frontend panels.

```
Priority (highest to lowest):
1. Environment variables: ODYSSEUS_FEATURE_<NAME>=true/false
2. OFFLINE_MODE=true → auto-disables internet features
3. data/features.json (editable via Settings UI)
4. Code defaults (most enabled)
```

**Internet-dependent features** (disabled by `OFFLINE_MODE=true`):
`email`, `web_search`, `research`, `gallery`, `compare`, `cookbook`, `webhooks`, `companion`

---

## 7. Error Handling Architecture

```
Custom Exceptions (core/exceptions.py):
├── SessionNotFoundError(session_id)
├── InvalidFileUploadError(message, filename)
├── LLMServiceError(message, endpoint)
└── WebSearchError(message, query)

Global Exception Handlers (in app.py):
├── SessionNotFoundError → 404 JSON
├── InvalidFileUploadError → 400 JSON
├── LLMServiceError → 502 JSON
├── WebSearchError → 502 JSON
├── HTTPException → passthrough
├── RequestTimeout → 504 JSON
└── Exception (catch-all) → 500 JSON
```

---

## 8. Companion/Pairing System

```
Companion Bridge (companion/routes.py):
│
├── GET  /api/companion/ping    → {ok, name, version, auth}
├── GET  /api/companion/info    → server identity + capabilities
├── GET  /api/companion/models  → owner-scoped model list
├── GET  /api/companion/pair    → Render pairing form (admin only)
├── POST /api/companion/pair    → Mint pairing token, return data-URI QR
│
└── Pairing Flow:
    1. Admin logs in → POST /api/companion/pair
    2. Server mints ApiToken (ody_ prefix)
    3. Returns QR code: {v:1, host, port, token}
    4. Phone scans QR → connects via Bearer token
    5. Owner scoping: token tied to admin's username
```

---

## 9. MCP Built-in Servers (`mcp_servers/`)

Each server follows the same pattern:
```python
from mcp.server import Server
server = Server("server_name")

@server.list_tools()
async def list_tools():
    return [Tool(name="tool_name", description="...", inputSchema={...})]

@server.call_tool()
async def call_tool(name, arguments):
    # ... implementation ...
    return [TextContent(type="text", text=result)]

# Run via asyncio stdio transport
```

**Shared constants** (`_common.py`):
- `MAX_OUTPUT_CHARS = 10_000`
- `MAX_READ_CHARS = 20_000`
- `SHELL_TIMEOUT = 60`
- `PYTHON_TIMEOUT = 30`
- `SEARCH_TIMEOUT = 30`
