# Horizon - AI Project Intelligence

A multi-user, workspace-based, real-time AI project intelligence system that transforms natural-language team conversations into structured tasks, risk predictions, and executive insights - automatically.

Inspired by Discord/Slack collaboration patterns combined with AI-driven task management, Horizon enables teams to chat naturally while an intelligent backend extracts actionable work items, predicts delivery risks, and surfaces insights - all scoped to isolated workspaces with role-based access control.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Core Features](#core-features)
3. [Realtime Architecture](#realtime-architecture)
4. [AI Capabilities](#ai-capabilities)
5. [Tech Stack](#tech-stack)
6. [Security & Permissions](#security--permissions)
7. [Architecture](#architecture)
8. [API Endpoints](#api-endpoints)
9. [Frontend Pages](#frontend-pages)
10. [How to Run](#how-to-run)
11. [Environment Variables](#environment-variables)
12. [How to Demo](#how-to-demo)

---

## Project Overview

Horizon is a full-stack AI project management platform built with React and FastAPI. It goes beyond traditional project management tools by embedding AI directly into the collaboration workflow:

- **Team members chat** in workspace channels - just like Slack or Discord.
- **AI extracts tasks** from every message: it classifies the domain, urgency, entities, and contacts automatically.
- **Duplicate detection** prevents redundant tasks by computing semantic similarity against existing work items.
- **Risk scoring** predicts the probability of task failure using historical features and ML models.
- **Alerts fire automatically** when risk thresholds are breached, tasks are blocked, or deadlines are missed.
- **Dashboards and risk views** give managers real-time visibility into project health.

All data is **workspace-scoped** - tasks, messages, risks, and alerts are isolated per workspace. Multiple users can collaborate in the same workspace with real-time WebSocket updates.

---

## Core Features

### Authentication
- JWT-based login and registration
- Persistent sessions via `localStorage` token storage
- Automatic 401 logout interceptor (expired tokens redirect to landing page)

### Multi-Workspace Support
- Create unlimited workspaces with name, description, and access type
- Switch between workspaces instantly - all page data reloads automatically
- Active workspace persisted across browser refreshes

### Workspace Access Types
| Type | Behavior |
|------|----------|
| 🔒 **Private** | Only admins can add members. Self-join shows "Ask an admin to add you." |
| 🌐 **Open** | Anyone with the workspace ID can look it up and join instantly via a "Join Workspace" button. |

### Real-Time Chat (WebSockets)
- Messages sent via REST are broadcast to all workspace members over WebSocket
- Other users see messages appear instantly without page refresh
- AI responses are broadcast to all connected clients

### Live Presence
- Green dots next to online members in the chat sidebar
- Presence updates on every connect and disconnect
- Presence clears when WebSocket disconnects

### AI-Generated Tasks from Chat
- Every chat message runs through the full AI pipeline
- Tasks are created or matched to existing tasks automatically
- Domain classification, urgency detection, entity and contact extraction
- Results displayed in an interactive AI analysis sidebar panel

### Risk Scoring
- Per-task risk scores with Low / Medium / High / Critical levels
- Workspace-level aggregate risk overview
- Manual risk predictor form for ad-hoc analysis
- Risk distribution bar chart on the dashboard

### Workspace Info & Invite Links
- Workspace dropdown shows **Workspace Info** panel with name and numeric ID
- **Copy ID** button copies workspace ID to clipboard (with "Copied!" feedback)
- **Copy Invite Link** button generates a shareable URL (`/join/{id}`) and copies it
- Invite links route directly to the join flow — if the user isn't logged in, they're sent to auth first, then the join auto-triggers after login
- Frontend parses `/join/:id` on mount via `window.location.pathname` (no React Router needed)

### Workspace Deletion (Admin Only)
- Admin can permanently delete a workspace (cascade: channels, messages, tasks, alerts, members)
- Confirmation modal with warning text
- All connected WebSocket clients receive a `workspace_deleted` event and are kicked
- Non-admin users' UI clears the deleted workspace automatically

### AI Bot Messages
- Every chat message gets a structured AI response showing:
  - Summary of the message
  - Task created/updated with similarity label
  - Risk score and level
  - Alert (if triggered)

---

## Realtime Architecture

Horizon uses **workspace-scoped WebSocket connections** for real-time collaboration:

```
Client                          Server
  │                               │
  ├── WS Connect ────────────────►│  /ws/workspace/{id}?token=JWT
  │                               │  → Authenticate via JWT
  │                               │  → Check membership or open access
  │                               │  → Accept connection
  │◄── presence_update ──────────┤  → Broadcast online user list
  │                               │
  ├── REST POST /messages ───────►│  → Persist message + run AI pipeline
  │◄── HTTP response (AI result)──┤  → Return result to sender
  │                               │
  │◄── chat_message (broadcast) ──┤  → WS broadcast to all workspace clients
  │◄── ai_response (broadcast) ───┤  → WS broadcast AI result to all clients
  │                               │
  │  (on disconnect)              │
  │◄── presence_update ──────────┤  → Broadcast updated online list
  │                               │
  │  (on workspace deletion)      │
  │◄── workspace_deleted ────────┤  → Notify all clients, close connections
```

**Key design decisions:**
- Messages are sent via **REST** (not WS) to ensure the AI pipeline processes them once - no duplicate tasks
- The REST endpoint then **broadcasts** the result to all WS clients for real-time visibility
- Presence updates are emitted on connect and disconnect events
- Workspace deletion broadcasts a `workspace_deleted` event before cascade-deleting data

---

## AI Capabilities

Horizon's AI pipeline processes every chat message through three ML modules:

### ML-1: NLP Classification & Entity Extraction
- **Zero-shot classification** using `distilbert-base-uncased-mnli` - classifies messages into domains (frontend, backend, devops, security, etc.) without training on project-specific data
- **Entity extraction** via spaCy `en_core_web_sm` - detects people, organizations, dates, and contacts
- **Urgency detection** from message language patterns

### ML-2: Task Linking & Similarity
- **Sentence embeddings** using `all-MiniLM-L6-v2` - encodes task titles into dense vectors
- **Cosine similarity** matching against existing tasks - prevents duplicate creation
- Labels: `NEW` (no match), `SIMILAR` (related task found), `DUPLICATE` (near-exact match, updates existing)

### ML-3: Risk Prediction
- **Random Forest Regressor** trained on task features (domain, urgency, history)
- **SHAP explanations** for risk scores - shows which features drive the prediction
- Outputs a 0–100% risk score mapped to Low / Medium / High / Critical levels

> AI augments the team - it does **not** replace human judgment. All AI outputs are visible and editable.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, Axios (JWT interceptors), CSS (Horizon dark design system), `createPortal` for modals |
| **Backend** | FastAPI, SQLAlchemy ORM, Alembic (migrations), python-dotenv |
| **Auth** | PyJWT (JSON Web Tokens), passlib + bcrypt for password hashing |
| **Database** | PostgreSQL 14+ |
| **Realtime** | WebSockets (FastAPI native), workspace-scoped connection manager |
| **ML** | PyTorch, Hugging Face Transformers, sentence-transformers, scikit-learn, SHAP, spaCy, pandas |
| **Visualization** | matplotlib, seaborn (backend plots), custom SVG (frontend charts) |

---

## Security & Permissions

### Role-Based Access
| Role | Capabilities |
|------|-------------|
| **Admin** | Full access: add/remove members, delete workspace, manage settings |
| **Member** | Chat, view tasks/dashboard/risk, leave workspace |

### Access Enforcement
- **Backend enforces all permissions** — the frontend only reflects what the API allows
- Private workspaces: only admins can add members via `POST /workspaces/{id}/members`
- Open workspaces: any authenticated user can self-join via `POST /workspaces/{id}/join`
- WebSocket connections check membership (or open access) before accepting
- All task, message, dashboard, and risk APIs validate workspace membership
- The last admin cannot leave a workspace (prevents orphaned workspaces)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React 18)                                     │
│  ├── LandingPage    — Public splash page                │
│  ├── AuthPage       — Login / Register (JWT)            │
│  ├── ChatPage       — AI chat + members sidebar         │
│  ├── TasksPage      — Kanban board with inline editing  │
│  ├── DashboardPage  — Stats, charts, alerts, tasks      │
│  └── RiskPage       — Risk predictor + workspace risk   │
├─────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                        │
│  ├── /auth/*         — Register, login, current user    │
│  ├── /workspaces/*   — CRUD, members, join, delete      │
│  ├── /messages       — Chat → AI pipeline               │
│  ├── /tasks/*        — CRUD, status updates             │
│  ├── /dashboard      — Aggregated stats                 │
│  ├── /risk/*         — Prediction + workspace overview  │
│  └── /ws/workspace/* — WebSocket (presence, broadcast)  │
├─────────────────────────────────────────────────────────┤
│  ML Modules (loaded at runtime — no training needed)    │
│  ├── ML-1: NLP      — Zero-shot classifier + entities  │
│  ├── ML-2: Tasks    — Semantic similarity engine        │
│  └── ML-3: Risk     — Random Forest + SHAP             │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL          — All data, workspace-scoped       │
└─────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account → returns JWT |
| POST | `/auth/login` | Login → returns JWT |
| GET | `/auth/me` | Current user info (requires token) |

### Workspaces
| Method | Path | Description |
|--------|------|-------------|
| GET | `/workspaces/` | List user's workspaces |
| POST | `/workspaces/` | Create workspace (creator becomes admin) |
| GET | `/workspaces/{id}` | Workspace details (requires membership) |
| GET | `/workspaces/{id}/lookup` | Public workspace lookup (any authenticated user) |
| GET | `/workspaces/{id}/members` | List workspace members |
| POST | `/workspaces/{id}/members` | Add member — admin only |
| DELETE | `/workspaces/{id}/members/{uid}` | Remove member — admin only, blocks last admin |
| POST | `/workspaces/{id}/join` | Self-join — open workspaces only |
| DELETE | `/workspaces/{id}` | Delete workspace — admin only, cascade delete |

### Chat & Tasks
| Method | Path | Description |
|--------|------|-------------|
| POST | `/messages` | Send message → AI pipeline (accepts `workspace_id`) |
| GET | `/messages/{channel_id}` | Retrieve channel messages (paginated) |
| GET | `/tasks` | List tasks (accepts `?workspace_id`) |
| PATCH | `/tasks/{id}/status` | Update task status |
| PATCH | `/tasks/{id}` | Update task fields (title, domain, urgency) |
| DELETE | `/tasks/{id}` | Delete task |

### Dashboard & Risk
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard` | Aggregated stats (accepts `?workspace_id`) |
| POST | `/risk/predict` | Standalone risk prediction |
| GET | `/risk/workspace/{id}` | Workspace-level risk overview |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/workspace/{id}?token=JWT` | Workspace real-time events (chat, presence, deletion) |
| `ws://host/ws/chat/{channel_id}?token=JWT` | Legacy channel-level chat (retained for compatibility) |

---

## Frontend Pages

| Page | Tab | Key Features |
|------|-----|-------------|
| **Landing** | - | Public splash with animated CTA, dark Horizon theme, subtle grid lines, edge glow orbs, horizon line, noise grain overlay, corner depth gradients |
| **Auth** | - | Login / Register forms, JWT token storage |
| **Chat** | Chat | AI chat input, message history, members sidebar with presence dots, AI analysis panel, voice UI (visual), custom domain management, add member modal (admin) |
| **Tasks** | Tasks | Kanban columns (Open → In Progress → Updated → Resolved), drag-and-click status updates, inline edit modal with domain chips + urgency selector + assignee avatars |
| **Dashboard** | Dashboard | Stat cards (messages, tasks, alerts, avg risk), risk distribution bar chart, recent alerts list, recent tasks table, Horizon futuristic theme (grid, glow orbs, scanlines, frosted glass) |
| **Risk** | Risk | Manual risk predictor form (title, domain, urgency, description), workspace risk overview card |

---

## How to Run

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+

### 1. Clone & Configure

```bash
git clone <repo-url>
cd AI-Driven-Project-Management
cp .env.example backend/.env
# Edit backend/.env - set POSTGRES_PASSWORD and other variables
```

### 2. Database

```sql
CREATE DATABASE ai_project_intelligence;
```

### 3. Backend

```bash
cd backend
python -m venv ../.venv

# Windows
..\.venv\Scripts\activate
# macOS/Linux
source ../.venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run database migrations
alembic upgrade head

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000` — interactive docs at `http://localhost:8000/docs`.

### 4. Frontend

```bash
cd frontend
npm install
npm start
```

Opens at `http://localhost:3000`.

---

## Environment Variables

Copy `.env.example` to `backend/.env` before running.

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DB` | Database name | `ai_project_intelligence` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | — |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `BACKEND_PORT` | FastAPI server port | `8000` |
| `REACT_APP_API_URL` | Backend URL for React app | `http://localhost:8000` |

---

## How to Demo

### Single-User Quick Start
1. Start the backend and frontend (see [How to Run](#how-to-run))
2. Open `http://localhost:3000` → click **Enter Horizon**
3. **Register** a new account
4. **Create a workspace** using the workspace dropdown (top bar) → name it, choose Private or Open
5. Go to the **Chat** tab → type messages like:
   - `"Backend login API is blocked due to CORS issue"`
   - `"Started implementing the payment module"`
   - `"Mark task 1 as resolved"`
6. Watch the AI panel show task extraction, risk scoring, and similarity analysis
7. Switch to **Tasks** → see the Kanban board with created tasks
8. Switch to **Dashboard** → see stats, risk charts, and alerts
9. Switch to **Risk** → run manual risk predictions

### Multi-User Real-Time Demo
1. Open two different browsers (e.g., Chrome and Firefox) or use incognito mode
2. Register **User A** in one browser, **User B** in the other
3. **User A** creates an **Open** workspace → note the workspace ID
4. **User B** clicks **Join Workspace** in the dropdown → enters the ID → joins
5. Both users open the **Chat** tab in the same workspace
6. **User A** sends a message → **User B** sees it appear in real time (green online dot visible)
7. **User B** sends a message → **User A** sees it immediately
8. **User A** deletes the workspace → **User B** sees "Workspace has been deleted" and the UI clears

### Key Things to Show
- Real-time message delivery across browsers
- Green presence dots showing online users
- AI task creation from natural language
- Risk scores on every message
- Open vs Private workspace access control
- Workspace deletion propagating to all connected users

---

## Detailed System Description

### What Horizon Does — End to End

**Horizon** is a complete AI-augmented project management platform designed for software teams. Here is exactly what happens when a user interacts with the system:

#### 1. Authentication Flow
When a user visits Horizon, they see an animated landing page. Clicking "Enter Horizon" leads to an authentication screen. Users register with a name, email, and password. The backend hashes the password with bcrypt, stores the user in PostgreSQL, and returns a JWT access token. This token is stored in `localStorage` and attached to every subsequent API request via an Axios interceptor. If the token expires, a 401 response triggers an automatic logout across the app via a `window` event.

#### 2. Workspace System
After login, the user enters the main application shell. The top bar contains a workspace selector dropdown. Users can:
- **Create** a workspace (private or open) - the creator automatically becomes the admin
- **Switch** between workspaces - all tabs (Chat, Tasks, Dashboard, Risk) reload with workspace-scoped data
- **Join** other workspaces by entering a workspace ID or clicking an invite link (`/join/{id}`) - open workspaces allow instant joining; private workspaces require an admin to add the user
- **Share** workspace access via the Workspace Info panel - copy the ID or a full invite link to clipboard
- **Leave** a workspace - the backend prevents the last admin from leaving
- **Delete** a workspace (admin only) - this cascade-deletes all channels, messages, tasks, alerts, and members, and notifies all connected WebSocket clients

#### 3. Chat & AI Pipeline
The Chat tab is where the core intelligence happens. When a user types a message:
1. The message is sent via REST `POST /messages` with the active `workspace_id`
2. The backend persists the message to PostgreSQL
3. The **AI Orchestrator** runs the message through three ML models in sequence:
   - **ML-1 (NLP)**: Classifies the domain (frontend, backend, devops, etc.), detects urgency, extracts entities (people, dates, organizations) and contacts
   - **ML-2 (Task Similarity)**: Encodes the message as a sentence embedding and computes cosine similarity against all existing tasks in the workspace. If similarity exceeds a threshold, the existing task is updated instead of creating a duplicate
   - **ML-3 (Risk)**: Predicts a 0-100% failure risk score using features like domain, urgency, and historical patterns. Generates SHAP-based explanations for the score
4. A task is created (or updated) in the database with all extracted metadata
5. If the risk score exceeds a threshold, an alert is created automatically
6. The AI result is returned to the sender via the HTTP response
7. The message and AI result are **broadcast** to all other workspace members via WebSocket - they see both appear in real time
8. The sender sees the AI analysis in a sidebar panel showing summary, task details, risk score, and any alerts

#### 4. Task Management
The Tasks tab displays a Kanban board with four columns: Open, In Progress, Updated, and Resolved. Tasks are created automatically from chat messages but can also be managed manually:
- Click a task to open an inline edit modal
- Change status by clicking column headers or using the modal
- Edit domain tags (with custom domain support), urgency level, and assignee
- Delete tasks via chat command (`delete task #5`) or the UI
- Update task titles via chat command (`update task #2: New title here`)

#### 5. Dashboard
The Dashboard tab provides an executive overview of the workspace:
- **Stat cards** showing total messages, tasks, alerts, and average risk score
- **Risk distribution bar chart** showing task counts by risk level (Low / Medium / High / Critical)
- **Recent alerts** list with severity badges
- **Recent tasks table** with ID, title, status, risk, and domain
- Visual design uses the Horizon theme: animated glow orbs, subtle grid background, scanline overlay, frosted glass effects on cards, and gradient accent borders

#### 6. Risk Analysis
The Risk tab offers two views:
- **Manual Risk Predictor**: Enter a task title, domain, urgency, and description → get an instant risk prediction with score and level
- **Workspace Risk Overview**: Aggregated risk metrics for the entire workspace (total tasks, average risk, risk distribution, highest-risk tasks)

#### 7. Real-Time Collaboration
WebSocket connections are established per workspace when users open the Chat tab:
- A `presence_update` event broadcasts the list of online user IDs on every connect/disconnect
- Chat messages sent via REST are broadcast to all workspace WS clients
- AI responses are broadcast to all workspace WS clients
- Workspace deletion broadcasts a `workspace_deleted` event, then disconnects all clients
- The frontend filters out own messages (displayed optimistically) and shows only messages from other users via WS

#### 8. Member Management
The Chat sidebar shows all workspace members with:
- User initials avatars with deterministic color from name
- Green presence dots for online users
- Role badges (admin / member)
- Admin users see an "Add Member" button to invite users by ID
- Admin users see the "Add Member" modal with role selection

---

## License

This project is provided for educational and demonstration purposes.
