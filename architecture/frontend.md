# Frontend Architecture

> **Detailed architecture of the Odysseus frontend (static/).**

---

## 1. Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Vanilla JavaScript (ES Modules) |
| **Markup** | HTML5 (SPA: `index.html`, `login.html`) |
| **Styling** | CSS3 (`style.css`), custom properties (variables) |
| **Build** | None — raw ES modules, no bundler |
| **Modules** | 70+ ES module files in `static/js/` |
| **Routing** | Hash-based client-side routing |
| **PWA** | Service Worker (`sw.js`) + manifest.json |
| **Dependencies** | Cached locally in `static/lib/` (no CDN) |

---

## 2. Module Architecture

```
static/
├── index.html              # Main SPA shell
├── login.html              # Auth page
├── landing.html            # Marketing page
├── app.js                  # Main entry: module loader, app initialization
├── style.css               # Global styles + theme variables
├── sw.js                   # Service Worker (PWA caching)
├── manifest.json           # PWA manifest
│
├── js/                     # 70+ ES modules
│   ├── init.js             # Auth check, privilege gating, startup sequence
│   ├── storage.js          # Safe localStorage API with key constants
│   ├── ui.js               # Toast, clipboard, scroll, debounce utilities
│   ├── chat.js             # Main chat submission, SSE streaming
│   ├── chatRenderer.js     # Message bubble rendering, code blocks, TTS
│   ├── chatStream.js       # SSE parsing, chunked response handling
│   ├── sessions.js         # Create/load/switch/fork/archive sessions
│   ├── theme.js            # 12+ themes, zero-flash application
│   ├── models.js           # Endpoint discovery, provider selection
│   ├── modelPicker.js      # Model picker dropdown UI
│   ├── modelSort.js        # Model sorting logic
│   ├── memory.js           # Long-term memory management UI
│   ├── skills.js           # Agent skill management UI
│   ├── rag.js              # RAG document management
│   ├── markdown.js         # Markdown → HTML with syntax highlighting
│   ├── settings.js         # Settings panel UI
│   ├── admin.js            # Admin panel (users, tokens, wipe)
│   ├── presets.js          # Chat preset management
│   ├── fileHandler.js      # File upload, attachment preview
│   ├── voiceRecorder.js    # Voice recording UI
│   ├── search.js           # Web search UI
│   ├── search-chat.js      # Chat message search (Ctrl+K)
│   ├── notes.js            # Notes/todos UI
│   ├── tasks.js            # Scheduled tasks UI
│   ├── gallery.js          # Image gallery
│   ├── galleryEditor.js    # Image editor
│   ├── document.js         # Document library
│   ├── documentLibrary.js  # Document library browser
│   ├── calendar.js         # Calendar UI
│   ├── emailInbox.js       # Email inbox UI
│   ├── emailLibrary.js     # Email library module
│   ├── signature.js        # Email signature management
│   ├── tts-ai.js           # AI TTS controls
│   ├── spinner.js          # Loading spinner component
│   ├── slashCommands.js    # Slash command autocomplete
│   ├── slashAutocomplete.js # Slash command suggestions
│   ├── keyboard-shortcuts.js # Global keyboard shortcuts
│   ├── escMenuStack.js     # Escape key menu stack
│   ├── modalManager.js     # Modal dialog management
│   ├── modalSnap.js        # Modal snapping behavior
│   ├── tileManager.js      # Tile layout management
│   ├── dragSort.js         # Drag-to-sort functionality
│   ├── section-management.js # UI section visibility
│   ├── sidebar-layout.js   # Sidebar layout management
│   ├── windowDrag.js       # Window dragging
│   ├── windowResize.js     # Window resizing
│   ├── group.js            # Chat grouping
│   ├── platform.js         # Platform detection
│   ├── langIcons.js        # Language icon mapping
│   ├── emojiPicker.js      # Emoji picker component
│   ├── censor.js           # Content censoring
│   ├── assistant.js        # Assistant configuration UI
│   ├── providers.js        # Provider management UI
│   ├── tourAutoplay.js     # Tour autoplay logic
│   ├── tourHints.js        # Tour hint system
│   ├── a11y.js             # Accessibility utilities
│   ├── cookbook.js         # Cookbook main UI
│   ├── cookbook-hwfit.js   # Hardware fitness detection
│   ├── cookbookDownload.js # Model download progress
│   ├── cookbookServe.js    # Model serve management
│   ├── cookbookRunning.js  # Running model display
│   ├── cookbook-diagnosis.js # Cookbook diagnostics
│   ├── codeRunner.js       # In-browser code runner
│   ├── editor/             # Rich document editor (40+ files)
│   ├── compare/            # A/B model comparison
│   ├── research/           # Deep research UI
│   ├── calendar/           # Calendar submodules
│   ├── color/              # Color picker utilities
│   ├── markdown/           # Markdown processing
│   ├── util/               # General utilities
│   └── MODULE_SUMMARY.md   # Module documentation
│
└── lib/                    # 3rd-party dependencies (cached locally)
```

---

## 3. Application Initialization Flow

```
1. index.html loads
     │
     ▼
2. app.js (main entry)
     ├── Import core modules: init, storage, ui, theme
     ├── Check auth status (init.js)
     │     ├── Not authenticated → redirect to login.html
     │     └── Authenticated → continue
     ├── Apply theme from localStorage (BEFORE body paint)
     ├── Initialize UI components:
     │     ├── Sidebar (sessions list)
     │     ├── Chat area
     │     ├── Model picker
     │     ├── File handler
     │     ├── Voice recorder
     │     └── Slash commands
     ├── Load sessions from API
     ├── Load active session messages
     ├── Register keyboard shortcuts
     └── Start background tasks (email polling, etc.)
```

---

## 4. Chat & Streaming Architecture

```
User types message → chat.js
    │
    ▼
chat.js: submitMessage()
    ├── Get current session, model, endpoint
    ├── Collect attachments (fileHandler.js)
    ├── Add user message to UI (chatRenderer.js)
    ├── POST /api/chat or EventSource /api/chat_stream
    │
    ▼
chatStream.js: handleStream()
    ├── Create EventSource connection
    ├── Parse SSE events:
    │     ├── "chunk" → Append to current message bubble
    │     ├── "tool_call" → Render tool invocation
    │     ├── "tool_result" → Render tool output
    │     ├── "done" → Mark message complete, trigger TTS
    │     └── "error" → Show error toast
    ├── 60s stall watchdog (max 3 nudges per turn)
    └── Auto-recovery on connection loss
    │
    ▼
chatRenderer.js: renderMessage()
    ├── Parse markdown (markdown.js → mdToHtml)
    ├── Syntax highlight code blocks
    ├── Render tool calls/results
    ├── Add AI TTS button
    ├── Render attachments
    └── Scroll to bottom
```

---

## 5. Theme System

### Architecture
```
theme.js
├── THEMES object: 12+ preset themes
│     Each: { --bg, --fg, --panel, --border, --red,
│              --keyword, --string, --comment, --function,
│              --number, --builtin, --variable, --params,
│              --bubble-user-bg, --bubble-ai-bg, ... }
│
├── Preset themes: dark, light, midnight, paper, cyberpunk,
│     retrowave, forest, ocean, ume, copper, terminal,
│     organs, lavender, gpt, claude, cute
│
├── Application (zero flash):
│     └── Inline <script> in <head> reads localStorage
│         and applies CSS vars BEFORE body paint
│
├── Dynamic favicon:
│     └── SVG rendered with current brand color (--red)
│
├── Background patterns: none, dots, rain, synapse,
│     embers, petals, constellations, perlin-flow, sparkles
│
├── Font family: mono (Fira Code), sans (system-ui), serif (Georgia)
│
└── Density: comfortable, compact, spacious
```

---

## 6. Service Worker (PWA)

```
sw.js (v326 — bump on schema changes)

Caching Strategies:
├── HTML pages:        stale-while-revalidate (instant load + bg refresh)
├── JS/CSS modules:    network-first (code changes show on reload)
├── Assets (fonts/img): cache-first with bg refresh
├── API responses:     never cached
└── Non-GET requests:  never cached

PWA Manifest (manifest.json):
├── name: "Odysseus"
├── display: "standalone"
├── Route-specific manifests: /calendar, /notes, /email
└── Icons: 192x192, 512x512
```

---

## 7. API Communication

```
All API calls via fetch() with credentials: 'same-origin'

Pattern:
  const res = await fetch('/api/endpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (data.ok) { ... } else { showToast(data.error, 'error'); }

Streaming:
  const es = new EventSource('/api/chat_stream?...');
  es.addEventListener('chunk', (e) => { ... });
  es.addEventListener('done', () => { es.close(); });
  es.addEventListener('error', () => { ... });
```

---

## 8. Editor Architecture (`static/js/editor/`)

The document editor is a rich canvas-based editor with 40+ files:

```
editor/
├── main.js              # Editor bootstrap
├── canvas.js            # Canvas rendering
├── layers.js            # Layer management
├── tools/               # Drawing/editing tools
├── toolbar.js           # Toolbar UI
├── history.js           # Undo/redo stack
├── selection.js         # Selection management
└── ...                  # 30+ more modules
```

---

## 9. State Management

Odysseus uses a **module-level singleton** pattern for state (no Redux/Vuex):

```
Pattern:
  // module-level state
  let _sessions = [];
  let _activeSession = null;

  // getter
  export function getActiveSession() { return _activeSession; }

  // setter with UI update
  export function setActiveSession(session) {
    _activeSession = session;
    renderSessionUI();
  }

Persistent State (localStorage via storage.js):
├── odysseus-theme        → Theme configuration
├── odysseus-prefs        → User preferences
├── odysseus-sidebar-state → Sidebar collapse state
└── odysseus-active-session → Last active session ID
```

---

## 10. Responsive Design

```
Breakpoints:
├── Mobile:    < 768px   (single column, bottom nav)
├── Tablet:    768-1024px (sidebar toggle)
└── Desktop:   > 1024px  (persistent sidebar)

Mobile adaptations:
├── Touch gestures (swipe sidebar)
├── Bottom navigation bar
├── Full-width chat bubbles
├── Floating action buttons
└── Installable as PWA (standalone display)
```

---

## 11. Feature Flag Integration

Frontend reads feature flags from API:
```javascript
// init.js loads features from /api/settings/features
const features = await fetch('/api/settings/features').then(r => r.json());

// UI components check flags before rendering
if (features.email) showEmailPanel();
if (features.calendar) initCalendar();
if (features.cookbook) showCookbookTab();
```

---

## 12. Editor Libraries (cached locally in `static/lib/`)

Dependencies are vendored (no CDN, no npm install for frontend):
- Code syntax highlighting library
- Markdown parsing library
- Calendar rendering library
- Image manipulation library
