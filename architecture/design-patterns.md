# Design Patterns

> **Design patterns, architectural decisions, and conventions used throughout the Odysseus codebase.**

---

## 1. Architectural Patterns

### 1.1 Layered Architecture
```
┌──────────────────────┐
│   Presentation       │  ← static/ (HTML, CSS, JS)
├──────────────────────┤
│   API Gateway        │  ← Middleware (Auth, CORS, Security, Timeout)
├──────────────────────┤
│   Route Handlers     │  ← routes/ (40+ modules)
├──────────────────────┤
│   Business Logic     │  ← src/ (Agent, Chat, Memory, Research)
├──────────────────────┤
│   Service Layer      │  ← services/ (Search, Memory, RAG, TTS)
├──────────────────────┤
│   Data Access        │  ← core/database.py + ChromaDB
├──────────────────────┤
│   Infrastructure     │  ← Docker, gosu, volumes
└──────────────────────┘
```

### 1.2 Dependency Injection (Manual)
Components are constructed in `app_initializer.py` and passed to route modules:

```python
# app_initializer.py
def initialize_managers(base_dir, rag_manager=None) -> Dict[str, Any]:
    memory_manager = MemoryManager(DATA_DIR)
    chat_processor = ChatProcessor(memory_manager, personal_docs_manager, memory_vector)
    chat_handler = ChatHandler(session_manager, memory_manager, chat_processor, ...)
    return {"memory_manager": memory_manager, "chat_handler": chat_handler, ...}

# Route setup
def setup_chat_routes(router, deps):
    chat_handler = deps["chat_handler"]
    # ... use chat_handler in endpoints
```

**Benefits**: Enables mocking for tests, clear dependency graph.

### 1.3 Repository Pattern
Data access is abstracted behind manager classes:
```
SessionManager    → abstracts session DB operations
MemoryManager     → abstracts memory JSON + vector operations
PresetManager     → abstracts preset JSON storage
APIKeyManager     → abstracts API key storage
```

### 1.4 Service Layer Pattern
Each capability is encapsulated as a service:
```
SearchService      → web search abstraction
MemoryService      → memory operations
ResearchService    → deep research pipeline
DocsService        → document indexing/RAG
ShellService       → command execution
TTSService         → text-to-speech
STTService         → speech-to-text
```

---

## 2. Creational Patterns

### 2.1 Singleton Pattern
Used for managers that should exist only once per process:
```python
# src/mcp_manager.py
class McpManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

Also used for:
- `RagManager` (via `rag_singleton.py`)
- `AuthManager` (created once in `app.py`)
- Module-level state in frontend JS modules

### 2.2 Factory Pattern (Route Setup)
Each route module exports a `setup_*_routes()` factory function:
```python
# routes/chat_routes.py
def setup_chat_routes(app_or_router, deps: dict):
    router = APIRouter(prefix="/api/chat", tags=["chat"])
    # ... define endpoints ...
    app_or_router.include_router(router)
```

---

## 3. Structural Patterns

### 3.1 Decorator Pattern
```python
# core/middleware.py
def require_admin(request: Request):
    """Raise 403 if current user isn't admin."""
    # ... check auth ...

# Usage in routes:
@router.post("/api/admin/wipe")
async def admin_wipe(request: Request):
    require_admin(request)
    # ... admin-only logic ...
```

### 3.2 Middleware Chain (Chain of Responsibility)
```
Request → RequestIdMiddleware
        → CORS Middleware
        → SecurityHeadersMiddleware
        → RequestTimeoutMiddleware
        → AuthMiddleware
        → Route Handler
        → Response
```

### 3.3 Facade Pattern
`ChatHandler` acts as a facade over the complex chat pipeline:
```python
class ChatHandler:
    def __init__(self, session_manager, memory_manager, chat_processor,
                 research_handler, preset_manager, upload_handler):
        # ... store dependencies ...

    async def process_message(self, ...):
        # Orchestrate: memory retrieval → agent loop → response
```

### 3.4 Adapter Pattern (LLM APIs)
`src/llm_core.py` provides adapters for different LLM APIs:
```
Native Anthropic API    ←→  AnthropicAdapter
OpenAI-compatible API   ←→  OpenAIAdapter
Fallback chain          ←→  FallbackAdapter
```

All adapt to the same interface:
```python
stream_llm(url, model, messages, ...) → AsyncGenerator[str]
```

---

## 4. Behavioral Patterns

### 4.1 Observer Pattern (Event Bus)
```python
# src/event_bus.py
class EventBus:
    _listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, handler: Callable):
        self._listeners.setdefault(event, []).append(handler)

    def emit(self, event: str, **data):
        for handler in self._listeners.get(event, []):
            handler(**data)
```

Used for: email notifications, task completion, memory updates.

### 4.2 Strategy Pattern
Different search providers implement the same interface:
```python
class SearchProvider:
    async def search(self, query: str, max_results: int) -> List[SearchResult]:
        raise NotImplementedError

class SearXNGProvider(SearchProvider): ...
class BraveProvider(SearchProvider): ...
class GoogleProvider(SearchProvider): ...
class TavilyProvider(SearchProvider): ...
class SerperProvider(SearchProvider): ...
```

### 4.3 Command Pattern (Agent Tools)
Each tool is a command with a defined interface:
```
ToolBlock { tag, args, content }
  → execute_tool_block(block, owner, session_id)
    → dispatch to MCP or native implementation
      → return result string
```

### 4.4 Template Method Pattern (MCP Servers)
All MCP servers follow the same template:
```python
server = Server("name")

@server.list_tools()    # Template method: list available tools
@server.call_tool()     # Template method: execute a tool
```

---

## 5. Concurrency Patterns

### 5.1 Thread-Safe Singleton with Lock
```python
# core/auth.py
class AuthManager:
    def __init__(self):
        self._sessions_lock = threading.RLock()   # Session mutations
        self._setup_lock = threading.Lock()        # First-run serialization
```

### 5.2 Dead-Host Cooldown (Circuit Breaker)
```python
# src/llm_core.py
DEAD_HOST_COOLDOWN = 20.0
_HOST_FAIL_THRESHOLD = 2

# 2 consecutive failures → 20s cooldown
# Any success resets counter immediately
# Thread-safe via _host_health_lock
```

### 5.3 Singleflight (Request Deduplication)
```python
# src/task_scheduler.py
async def _cached(key, ttl, fetch):
    # Concurrent callers for same key share ONE fetch() call
    # Exceptions propagate to all waiters, don't poison cache
```

### 5.4 Lazy Initialization
```python
# core/session_manager.py
class SessionManager:
    def load_sessions(self):
        # Load only metadata (top 100), not messages
        # Messages hydrated on demand via get_session()
```

---

## 6. Frontend Patterns

### 6.1 Module Revealing Pattern
```javascript
// static/js/storage.js
let _cache = {};

export function getItem(key) {
    if (!(key in _cache)) {
        _cache[key] = JSON.parse(localStorage.getItem(key));
    }
    return _cache[key];
}

export function setItem(key, value) {
    _cache[key] = value;
    localStorage.setItem(key, JSON.stringify(value));
}
```

### 6.2 Observer Pattern (SSE Events)
```javascript
// chatStream.js
const es = new EventSource('/api/chat_stream?...');
es.addEventListener('chunk', handleChunk);
es.addEventListener('tool_call', handleToolCall);
es.addEventListener('tool_result', handleToolResult);
es.addEventListener('done', handleDone);
es.addEventListener('error', handleError);
```

### 6.3 Publish-Subscribe (Event Bus)
```javascript
// Module-level event system
const listeners = {};
export function on(event, fn) { ... }
export function emit(event, data) { ... }
```

### 6.4 Zero-Flash Theme Application
```html
<!-- In <head> of index.html — runs before body paint -->
<script>
  (function() {
    const theme = JSON.parse(localStorage.getItem('odysseus-theme'));
    if (theme) {
      Object.entries(theme).forEach(([k, v]) => {
        document.documentElement.style.setProperty(k, v);
      });
    }
  })();
</script>
```

---

## 7. Data Patterns

### 7.1 Owner Scoping
Every resource has an `owner` field. Queries filter by owner:
```python
# All route queries:
db.query(Model).filter(Model.owner == current_user)

# Middleware sets current_user:
request.state.current_user = username
```

### 7.2 Encrypted Column at Rest
```python
# core/database.py
class EncryptedText(TypeDecorator):
    """Fernet-encrypted text column. Transparent to consumers."""
    def process_bind_param(self, value, dialect):
        return encrypt(value)   # Write: plaintext → encrypted

    def process_result_value(self, value, dialect):
        return decrypt(value)   # Read: encrypted → plaintext
```

### 7.3 Atomic JSON Writes
```python
# core/atomic_io.py
def atomic_write_json(path, data):
    """Write JSON atomically: write to temp file, then rename."""
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)  # Atomic on POSIX
```

### 7.4 Prefix-Based Token Cache
```python
# API tokens: ody_<prefix><hash>
# In-memory cache: {prefix → (full_hash, owner, scopes)}
# O(1) lookup instead of O(n) bcrypt verification
```

### 7.5 Hybrid BM25 + Vector Retrieval
```
memory retrieval = α * BM25_score + (1-α) * vector_similarity
where α ≈ 0.6 (keyword weight higher)
+ category_boost (1.2x-1.4x for identity/contact/preference)
+ recency_tiebreaker (max 5%)
→ threshold gate → top-k
```

---

## 8. Error Handling Patterns

### 8.1 Custom Exception Hierarchy
```python
SessionNotFoundError      → 404
InvalidFileUploadError    → 400
LLMServiceError           → 502
WebSearchError            → 502
```

### 8.2 Global Exception Handlers
```python
@app.exception_handler(SessionNotFoundError)
async def session_not_found(request, exc):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
```

### 8.3 Graceful Degradation
```python
# ChromaDB offline? Fall back to BM25 only
try:
    memory_vector = MemoryVectorStore(DATA_DIR)
except Exception:
    logger.warning("MemoryVectorStore DEGRADED")
    memory_vector = None

# GPU not available? Use CPU
if not gpu_available:
    use_cpu_fallback()
```

---

## 9. Testing Patterns

### 9.1 Dependency Injection for Testing
```python
# Production:
chat_handler = ChatHandler(session_manager, memory_manager, ...)

# Test:
mock_session_manager = MockSessionManager()
chat_handler = ChatHandler(mock_session_manager, ...)
```

### 9.2 pytest Fixtures
```python
@pytest.fixture
def auth_manager(tmp_path):
    auth_path = tmp_path / "auth.json"
    return AuthManager(str(auth_path))

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()
```

### 9.3 Async Test Support
```python
@pytest.mark.asyncio
async def test_chat_stream():
    async for chunk in stream_llm(...):
        assert chunk is not None
```
