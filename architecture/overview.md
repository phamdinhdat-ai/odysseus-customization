# Architecture Overview

> **High-level architecture of the Odysseus AI workspace system.**

---

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser / PWA)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Chat UI │ │  Editor  │ │ Calendar │ │  Email   │ │ Settings │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       └─────────────┴────────────┴────────────┴────────────┘         │
│                         │ fetch() + SSE                              │
│                    Service Worker (sw.js)                            │
└─────────────────────────┼────────────────────────────────────────────┘
                          │ HTTP/1.1 + SSE
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FASTAPI APPLICATION (app.py)                      │
│                                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐   │
│  │  Middleware  │  │  Auth Layer  │  │   Route Handlers (40+)    │   │
│  │  - CORS      │  │  - Cookie    │  │   /api/chat               │   │
│  │  - Security  │  │  - Bearer    │  │   /api/sessions           │   │
│  │  - RequestID │  │  - 2FA       │  │   /api/memory             │   │
│  │  - Timeout   │  │  - Privilege │  │   /api/documents          │   │
│  └─────────────┘  └──────────────┘  │   /api/email ...          │   │
│                                      └────────┬──────────────────┘   │
│                                               │                      │
│  ┌────────────────────────────────────────────┼──────────────────┐   │
│  │              BUSINESS LOGIC LAYER (src/)   │                   │   │
│  │                                            ▼                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │   │
│  │  │  Agent Loop  │  │ Chat Processor│  │   LLM Core       │    │   │
│  │  │  - Tool Parse│  │ - BM25 Memory │  │   - API Adapters │    │   │
│  │  │  - Execution │  │ - Vector      │  │   - Caching      │    │   │
│  │  │  - Multi-Rnd │  │ - RAG Inject  │  │   - Dead-Host    │    │   │
│  │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘    │   │
│  │         │                 │                    │              │   │
│  │         ▼                 ▼                    ▼              │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │                  MCP Manager                          │    │   │
│  │  │         (stdio subprocess / SSE connections)          │    │   │
│  │  └──────────────────────┬───────────────────────────────┘    │   │
│  └─────────────────────────┼────────────────────────────────────┘   │
└────────────────────────────┼────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   ChromaDB   │  │   SearXNG    │  │     ntfy     │
│  (Vector DB) │  │  (Search)    │  │(Notifications│
│   :8100/8000 │  │   :8080      │  │   :8091      │
└──────────────┘  └──────────────┘  └──────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│             DATA STORES (data/)               │
│  ┌────────────┐ ┌──────────┐ ┌────────────┐  │
│  │  app.db    │ │ memory   │ │ uploads/   │  │
│  │ (SQLite)   │ │ .json    │ │ personal_  │  │
│  │            │ │          │ │ docs/      │  │
│  └────────────┘ └──────────┘ └────────────┘  │
│  ┌────────────┐ ┌──────────┐ ┌────────────┐  │
│  │ auth.json  │ │sessions  │ │settings    │  │
│  │            │ │.json     │ │.json       │  │
│  └────────────┘ └──────────┘ └────────────┘  │
└──────────────────────────────────────────────┘
```

---

## Layer Architecture

```
┌─────────────────────────────────────────────────┐
│                 PRESENTATION                     │
│  static/ (HTML + CSS + Vanilla JS ES Modules)    │
│  PWA: Service Worker + manifest.json             │
├─────────────────────────────────────────────────┤
│                 API GATEWAY                      │
│  Middleware: CORS, Security Headers, Auth,       │
│  Request ID, Timeout (45s)                       │
├─────────────────────────────────────────────────┤
│                 ROUTE LAYER                      │
│  40+ route modules, feature-flag gated           │
│  Pattern: setup_*_routes(router, deps)           │
├─────────────────────────────────────────────────┤
│              BUSINESS LOGIC                      │
│  Agent Loop, Chat Processor, LLM Core,           │
│  Memory, Research, Documents, Calendar, Email    │
├─────────────────────────────────────────────────┤
│              SERVICE LAYER                       │
│  Search, Memory, RAG, TTS, STT, Shell,           │
│  Research, YouTube, MCP Manager                  │
├─────────────────────────────────────────────────┤
│              DATA LAYER                          │
│  SQLAlchemy ORM (SQLite), ChromaDB (Vectors),    │
│  JSON Files (Auth, Settings, Memory)             │
├─────────────────────────────────────────────────┤
│            INFRASTRUCTURE                        │
│  Docker, gosu, GPU overlays, SSH, tmux           │
└─────────────────────────────────────────────────┘
```

---

## Request Lifecycle

```
1. REQUEST ARRIVES
   │
   ▼
2. RequestIdMiddleware
   └─ Assign X-Request-Id (from header or generated)
   │
   ▼
3. CORS Middleware
   └─ Validate Origin, set CORS headers
   │
   ▼
4. SecurityHeadersMiddleware
   └─ CSP (with nonce), X-Frame-Options, Referrer-Policy
   │
   ▼
5. RequestTimeoutMiddleware
   └─ 45s hard timeout (exempt: chat, shell stream, research, uploads)
   │
   ▼
6. AuthMiddleware
   ├─ Check LOCALHOST_BYPASS (if enabled + loopback)
   ├─ Check odysseus_session cookie → validate token
   ├─ Check Authorization: Bearer ody_... → prefix cache lookup → bcrypt verify
   ├─ Check X-Odysseus-Internal-Token header (for agent loopback)
   ├─ Set request.state.current_user
   └─ Apply rate limiting
   │
   ▼
7. ROUTE HANDLER
   ├─ get_current_user(request)
   ├─ require_admin(request) [if admin-gated]
   ├─ Business logic (chat, agent, memory, etc.)
   └─ Return Response / StreamingResponse
   │
   ▼
8. RESPONSE
   └─ RequestIdMiddleware logs: method, path, status, duration
```

---

## Component Dependency Graph

```
app.py
  ├── AuthManager (core/auth.py)
  │     ├── auth.json → users, passwords (bcrypt)
  │     └── sessions.json → token → {username, expiry}
  │
  ├── AppInitializer (src/app_initializer.py)
  │     ├── SessionManager (core/session_manager.py)
  │     │     └── Database (SQLAlchemy → SQLite app.db)
  │     ├── MemoryManager (src/memory.py)
  │     │     └── memory.json + MemoryVectorStore (ChromaDB)
  │     ├── SkillsManager (services/memory/skills.py)
  │     ├── PersonalDocsManager (src/personal_docs.py)
  │     │     └── ChromaDB RAG collection
  │     ├── ChatProcessor (src/chat_processor.py)
  │     │     ├── MemoryManager (BM25 keyword retrieval)
  │     │     └── MemoryVectorStore (vector similarity)
  │     ├── ChatHandler (src/chat_handler.py)
  │     │     ├── SessionManager
  │     │     ├── ChatProcessor
  │     │     ├── ResearchHandler
  │     │     └── PresetManager
  │     ├── ModelDiscovery (src/model_discovery.py)
  │     └── ResearchHandler (src/research_handler.py)
  │
  ├── Route Registration (40+ modules)
  │     Each: setup_*_routes(router, {dependencies})
  │
  └── Services (async initialization)
        ├── RAG Manager (ChromaDB document search)
        ├── TTS/STT Services
        ├── MCP Manager (server connections)
        ├── TaskScheduler (cron tasks)
        └── WebhookManager (outgoing webhooks)
```

---

## Data Flow: Chat with Agent

```
User Message
    │
    ▼
ChatHandler.process_message()
    │
    ├── ChatProcessor.process()
    │     ├── _hybrid_retrieve() → BM25 + vector memories
    │     └── RAG search → relevant documents
    │
    ├── Agent Loop (if agent enabled)
    │     │
    │     ▼
    │   stream_llm() with tool definitions
    │     │
    │     ▼
    │   Parse response for tool blocks
    │     │
    │     ├── TOOL FOUND?
    │     │     YES → execute_tool_block()
    │     │     │       ├── MCP dispatch or native implementation
    │     │     │       └── Inject result back into context
    │     │     │       └── Loop (max 10 rounds)
    │     │     NO  → Stream final response to user
    │     │
    │     ▼
    │   Save messages to session
    │
    └── SSE Stream → Client
```

---

## Key Integration Points

| Integration | Protocol | Direction | Purpose |
|------------|----------|-----------|---------|
| LLM APIs | HTTP (OpenAI-compat) | Outbound | Model inference |
| ChromaDB | HTTP (REST) | Outbound | Vector storage & search |
| SearXNG | HTTP (REST) | Outbound | Privacy-respecting web search |
| ntfy | HTTP (REST) | Outbound | Push notifications |
| MCP Servers | stdio / SSE | Outbound | Tool execution |
| IMAP/SMTP | TCP | Outbound | Email polling & sending |
| CalDAV | HTTP (WebDAV) | Outbound | Calendar sync |
| Ollama | HTTP (OpenAI-compat) | Outbound | Local model inference |
| vLLM/SGLang | HTTP (OpenAI-compat) | Outbound | GPU model serving |
| HuggingFace | HTTPS | Outbound | Model catalog & downloads |
