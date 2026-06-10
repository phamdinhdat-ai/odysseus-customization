# Data Flow Architecture

> **How data flows through the Odysseus system — from user input to AI response and back.**

---

## 1. Chat Request Flow (with Agent)

```
┌─────────────────────────────────────────────────────────────────────┐
│ USER: "Summarize my latest emails and create a todo"                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 1. FRONTEND (chat.js)                                               │
│    └─ POST /api/chat  {                                            │
│         session_id, message, model, endpoint, agent_enabled: true   │
│       }                                                             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. AUTH MIDDLEWARE                                                  │
│    ├─ Validate cookie/bearer token                                  │
│    ├─ Set request.state.current_user = "datpham"                    │
│    └─ Check privileges (can_use_agent)                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. CHAT HANDLER (src/chat_handler.py)                               │
│    ├─ Load session from DB (SessionManager.get_session)             │
│    ├─ Build message list (system + history + user)                  │
│    └─ Delegate to ChatProcessor                                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. CHAT PROCESSOR (src/chat_processor.py)                           │
│    ├─ _hybrid_retrieve(user_message, all_memories, k=5)             │
│    │     ├─ BM25 keyword scoring (IDF from memory corpus)           │
│    │     ├─ Vector similarity (ChromaDB, if healthy)                │
│    │     └─ Return top-5 relevant memories                          │
│    ├─ RAG search: query personal documents (if RAG enabled)         │
│    ├─ Inject memories + RAG results as system context               │
│    └─ Return augmented message list                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. AGENT LOOP (src/agent_loop.py)                                   │
│    ┌──────────────────────────────────────────────────────────┐    │
│    │ ROUND 1:                                                  │    │
│    │  ├─ Build system prompt (preamble + rules + tools)        │    │
│    │  ├─ stream_llm(messages) → LLM generates:                 │    │
│    │  │                                                        │    │
│    │  │   ```list_emails                                       │    │
│    │  │   max_results: 5                                       │    │
│    │  │   unread_only: true                                    │    │
│    │  │   ```                                                  │    │
│    │  │                                                        │    │
│    │  ├─ parse_tool_blocks() → [ToolBlock("list_emails", ...)] │    │
│    │  ├─ execute_tool_block() → MCP email_server               │    │
│    │  │     └─ Returns: "1. UID:90186 Subject:Meeting..."      │    │
│    │  └─ Inject result into context                            │    │
│    ├──────────────────────────────────────────────────────────┤    │
│    │ ROUND 2:                                                  │    │
│    │  ├─ stream_llm(messages + tool_result) → LLM generates:   │    │
│    │  │                                                        │    │
│    │  │   ```manage_notes                                       │    │
│    │  │   action: add                                          │    │
│    │  │   title: "Prepare for meeting"                         │    │
│    │  │   note_type: checklist                                 │    │
│    │  │   due_date: 2026-06-11                                 │    │
│    │  │   ```                                                  │    │
│    │  │                                                        │    │
│    │  ├─ execute_tool_block() → note_manager.add()             │    │
│    │  │     └─ Returns: "Note created: Prepare for meeting"    │    │
│    │  └─ Inject result into context                            │    │
│    ├──────────────────────────────────────────────────────────┤    │
│    │ ROUND 3 (Final):                                          │    │
│    │  ├─ stream_llm(messages + all_results)                    │    │
│    │  └─ LLM generates final summary (no more tools)           │    │
│    └──────────────────────────────────────────────────────────┘    │
│                                                                     │
│    Result: "You have 3 unread emails: Meeting tomorrow, ...         │
│             I've created a todo 'Prepare for meeting' for you."     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. SESSION MANAGER (core/session_manager.py)                        │
│    ├─ Save user message to DB                                       │
│    ├─ Save AI response to DB                                        │
│    └─ Save tool calls as metadata                                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. RESPONSE → FRONTEND                                              │
│    {                                                                │
│      message: "You have 3 unread emails...",                        │
│      tool_calls: [{tool, args, result}, ...],                       │
│      session_id: "abc123"                                           │
│    }                                                                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. FRONTEND RENDERING (chatRenderer.js)                             │
│    ├─ Render AI message bubble with markdown                        │
│    ├─ Render tool call expand/collapse sections                     │
│    ├─ Update session message count                                  │
│    └─ Scroll to bottom                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Streaming Chat Flow (SSE)

```
Client (EventSource)                    Server (FastAPI StreamingResponse)
     │                                         │
     │  GET /api/chat_stream?session_id=...    │
     │────────────────────────────────────────>│
     │                                         │
     │                  ┌──────────────────────┤
     │                  │ Build context        │
     │                  │ (memories + RAG)     │
     │                  └──────────┬───────────┤
     │                             │           │
     │  event: status              │           │
     │  data: {"status":"thinking"│           │
     │<────────────────────────────┤           │
     │                             │           │
     │                  ┌──────────▼───────────┤
     │                  │ stream_llm()         │
     │                  │ yields token chunks  │
     │                  └──────────┬───────────┤
     │                             │           │
     │  event: chunk               │           │
     │  data: {"text":"You "}      │           │
     │<────────────────────────────┤           │
     │                             │           │
     │  event: chunk               │           │
     │  data: {"text":"have "}     │           │
     │<────────────────────────────┤           │
     │                             │           │
     │  ... (more chunks) ...      │           │
     │                             │           │
     │  event: tool_call           │           │
     │  data: {"tool":"list_emails"│          │
     │<────────────────────────────┤           │
     │                             │           │
     │  event: tool_result         │           │
     │  data: {"result":"..."}    │           │
     │<────────────────────────────┤           │
     │                             │           │
     │  ... (more chunks) ...      │           │
     │                             │           │
     │  event: done                │           │
     │  data: {"session_id":"..."} │           │
     │<────────────────────────────┤           │
     │                             │           │
     │  EventSource.close()        │           │
```

---

## 3. Memory Retrieval Flow

```
User message: "What's my favorite color?"

┌─────────────────────────────────────────────────────────────────┐
│ ChatProcessor._hybrid_retrieve(message, all_memories, k=5)      │
│                                                                  │
│ STEP 1: Tokenize query                                           │
│   └─ _content_tokens("What's my favorite color?")                │
│      → ["what", "favorite", "color"]  (after stopword removal)  │
│                                                                  │
│ STEP 2: Build corpus statistics                                  │
│   └─ For each memory in all_memories:                            │
│       ├─ Tokenize memory text                                    │
│       └─ Count document frequency per token                      │
│                                                                  │
│ STEP 3: BM25 Score per memory                                    │
│   └─ For each memory:                                            │
│       score = Σ idf(token) * tf_norm(token)                      │
│       where:                                                     │
│         idf = log((N - df + 0.5) / (df + 0.5) + 1)              │
│         tf_norm = (tf * (k1+1)) / (tf + k1*(1-b+b*len/avg_len)) │
│                                                                  │
│ STEP 4: Vector Similarity (if ChromaDB available)                │
│   └─ Query embedding → cosine similarity against all memories    │
│                                                                  │
│ STEP 5: Category-Aware Boost                                     │
│   └─ Check for preference keywords → 1.2x boost                  │
│                                                                  │
│ STEP 6: Combine scores (BM25 + vector)                           │
│   └─ Normalize + weight (keyword: 0.6, vector: 0.4)              │
│   └─ Add recency tiebreaker (max 5% contribution)               │
│                                                                  │
│ STEP 7: Threshold gate → top-5 results                           │
│   └─ Return: [{id, text, score, category}, ...]                  │
└─────────────────────────────────────────────────────────────────┘

Result injected as system context:
"Relevant memories:
- User's favorite color is blue (preference)
- User prefers dark mode themes (preference)"
```

---

## 4. Email Polling Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ EmailPoller (routes/email_pollers.py)                             │
│                                                                   │
│ 1. STARTUP:                                                       │
│    ├─ Read ODYSSEUS_INPROCESS_POLLERS env var (default: 1)       │
│    └─ If enabled, create asyncio task for polling loop           │
│                                                                   │
│ 2. POLL LOOP (every N minutes, configurable per account):         │
│    ├─ Query email_accounts from DB                                │
│    ├─ For each enabled account:                                   │
│    │     ├─ Connect to IMAP server                                │
│    │     ├─ Select INBOX                                          │
│    │     ├─ Search for new messages (since last poll)             │
│    │     └─ For each new message:                                 │
│    │           ├─ Fetch full content                              │
│    │           ├─ AI Triage (optional):                           │
│    │           │     ├─ Urgency detection                         │
│    │           │     ├─ Auto-tagging                              │
│    │           │     ├─ Auto-summary                              │
│    │           │     ├─ Auto-reply draft                          │
│    │           │     └─ Spam detection                            │
│    │           ├─ Save to DB                                      │
│    │           └─ Send notification (ntfy/browser)                │
│    └─ Update last_poll timestamp per account                      │
│                                                                   │
│ 3. NOTIFICATION:                                                  │
│    └─ Server-Sent Event to connected clients                     │
│       or ntfy push notification                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Scheduled Task Execution Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ TaskScheduler (src/task_scheduler.py)                             │
│                                                                   │
│ 1. STARTUP:                                                       │
│    ├─ Read ODYSSEUS_INPROCESS_TASKS env var (default: 1)         │
│    └─ If enabled, start scheduler loop                            │
│                                                                   │
│ 2. SCHEDULER LOOP (every 60 seconds):                             │
│    ├─ Query scheduled_tasks from DB                               │
│    │     WHERE enabled = true AND next_run <= now()               │
│    │                                                              │
│    ├─ For each due task:                                          │
│    │     ├─ Compute next_run (for recurrence)                     │
│    │     ├─ Acquire lock (prevent duplicate execution)            │
│    │     ├─ Execute task:                                         │
│    │     │     ├─ Create temporary session                         │
│    │     │     ├─ Run agent loop with task prompt                 │
│    │     │     ├─ Save results                                    │
│    │     │     └─ Send notification                               │
│    │     └─ Update task: next_run, last_run, last_result          │
│    │                                                              │
│    └─ Shared TTL cache for external data fetches                 │
│       (deduplicates Miniflux unreads, MCP snapshots, etc.)       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Deep Research Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ Deep Research (src/deep_research.py)                              │
│                                                                   │
│ 1. User submits research question                                 │
│    └─ POST /api/research {question, depth, breadth}               │
│                                                                   │
│ 2. PLANNING PHASE:                                                │
│    ├─ LLM generates research plan                                 │
│    ├─ Break question into sub-questions                           │
│    └─ Identify search queries per sub-question                    │
│                                                                   │
│ 3. EXECUTION PHASE (per sub-question):                            │
│    ├─ Search web (SearXNG/Brave/Google)                          │
│    ├─ Fetch and extract page content                              │
│    ├─ Score relevance                                             │
│    └─ Extract key facts and citations                             │
│                                                                   │
│ 4. SYNTHESIS PHASE:                                               │
│    ├─ LLM synthesizes all findings                                │
│    ├─ Generate structured report (markdown)                       │
│    └─ Add citations and source links                              │
│                                                                   │
│ 5. VISUALIZATION:                                                 │
│    ├─ Generate visual report (HTML/Mermaid diagrams)              │
│    └─ Stream progress via SSE                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Data Persistence Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ DATA LAYER                                                       │
│                                                                   │
│ ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│ │  SQLite (app.db) │  │  ChromaDB        │  │  JSON Files       │ │
│ │                  │  │  (Vector Store)  │  │                  │ │
│ │  • sessions      │  │  • memory_vector │  │  • auth.json     │ │
│ │  • chat_messages │  │  • rag_documents │  │  • sessions.json │ │
│ │  • documents     │  │  • tool_index    │  │  • memory.json   │ │
│ │  • notes         │  │                  │  │  • settings.json │ │
│ │  • api_tokens    │  └──────────────────┘  │  • presets.json  │ │
│ │  • mcp_servers   │                        │  • features.json │ │
│ │  • model_endpoints│                       │  • user_prefs    │ │
│ │  • scheduled_tasks│                      └──────────────────┘ │
│ │  • gallery_images │                                             │
│ │  • email_accounts │  ┌──────────────────┐                      │
│ │  • calendar_events│  │  File System     │                      │
│ │  • contacts       │  │                  │                      │
│ └─────────────────┘  │  • uploads/       │                      │
│                       │  • personal_docs/ │                      │
│                       │  • generated_imgs/│                      │
│                       │  • tts_cache/    │                      │
│                       │  • mail-attach/  │                      │
│                       │  • skills/       │                      │
│                       └──────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. Request-Response Envelope

All API responses use a standardized envelope:

```json
// Success
{
  "ok": true,
  "data": { ... },
  "request_id": "a1b2c3d4"
}

// Error
{
  "ok": false,
  "error": "Session not found",
  "error_code": "SESSION_NOT_FOUND",
  "request_id": "a1b2c3d4"
}
```
