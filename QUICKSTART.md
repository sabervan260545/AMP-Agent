# AMP-Agent Platform — Quick Start Guide

## ⚠️ Minimal Release Mode (Important — read first)

This public release is intentionally shipped in **Minimal Release Mode**:

- Only the **coordination layer** is shipped as runnable code
  (Flask `backend`, React `frontend`, Postgres, knowledge base).
- The 9 AMP prediction / generation microservices under
  `services/*/` are **directory placeholders** — each one contains
  *only* an `IMPLEMENTATION.md` describing the upstream model, the
  expected API contract, the model weights and how to restore the
  full implementation. No `app.py`, `Dockerfile` or trained weights
  are shipped.
- In `docker-compose.yml` every microservice block is **commented
  out** and `backend.depends_on` lists only `postgres`. Running
  `docker compose up -d` will therefore start `backend` + `frontend`
  + `postgres` + `knowledge-builder` only; all AMP prediction and
  generation routes will return transport-level errors because their
  target services are not up.

**What you can demo out-of-the-box**

- Overall repository layout and documentation
- Flask backend health (`/api/health`) and route map
- Frontend UX shell, chat panel, layout and knowledge-base retrieval
- Knowledge-base (re)build via `knowledge_builder/rebuild_index.py`

**What requires re-deployment by you**

Any end-to-end AMP generation, filtering, MIC / hemolysis / CPP
scoring, or structure prediction task. Per service, follow the
corresponding `services/*/IMPLEMENTATION.md`:

1. Clone the upstream repository referenced in `IMPLEMENTATION.md`
   into `services/<name>/` (overwrite the placeholder directory).
2. Download the model weights listed there into `./data/models/<name>/`.
3. Un-comment the matching block in `docker-compose.yml` and re-add
   the service name to `backend.depends_on`.
4. `docker compose build <name> && docker compose up -d <name>`.

For a third-party drop-in replacement, you only need to match the
**Expected API contract** table in `IMPLEMENTATION.md` (route, method,
request / response JSON keys) and expose the service on the port
listed there.

---

## 📌 Quick Reference Card

| Action | Command | Notes |
|--------|---------|-------|
| **Start all services** | `docker compose up -d` | Backend + microservices |
| **Start backend only** | `docker compose up -d backend` | Flask backend |
| **Start frontend** | `cd frontend && npm run dev` | Vite dev server |
| **Stop all services** | `docker compose stop` | Keeps containers |
| **Restart backend** | `docker compose restart backend` | After code changes |
| **Stop frontend** | `Ctrl+C` or `lsof -ti:3000 \| xargs kill -9` | Port-scoped kill |
| **Backend logs** | `docker compose logs -f backend` | Live log stream |
| **Container status** | `docker compose ps` | All containers |
| **Full teardown** | `docker compose down -v` | ⚠️ Deletes volumes! |

**Default ports**:
- Frontend: `http://localhost:3000`
- Backend (Flask): `http://localhost:5000`

---

## 🧠 First-time Setup: Build the Knowledge Base

The repository **does not ship the pre-built vector store** (`chroma.sqlite3`,
~82 MB) to keep the release lightweight and license-clean. On a fresh
checkout you must rebuild the embedding index **once** before starting the
backend, otherwise knowledge retrieval will return empty results.

```bash
cd <PROJECT_ROOT>
python knowledge_builder/rebuild_index.py
```

What it does:
- Reads the source corpora under `knowledge_builder/integrated_knowledge_base/`
  (literature, MIC / CPP / hemolysis datasets, statistics, motif patterns).
- Encodes every entry with `sentence-transformers` and writes a local
  Chroma DB to `knowledge_builder/integrated_knowledge_base/vector_store/`.
- Takes ~3–10 min on CPU, <2 min with a GPU.

You only need to re-run it when the underlying corpora change; the resulting
`vector_store/` directory is git-ignored and persists across restarts.

---

## 🚀 Service Startup

### 1. Start the backend (Flask)

#### Option A: Docker Compose (recommended)

```bash
cd <PROJECT_ROOT>
docker compose up -d backend
```

Health check:
```bash
curl http://localhost:5000/api/health
# Expected: {"service":"AMP-Agent Backend","status":"ok","version":"3.0"}
```

#### Option B: Run Python directly

```bash
cd <PROJECT_ROOT>/backend
source /path/to/your/venv/bin/activate
python app.py
```

**Notes**:
- Backend runs on `http://localhost:5000`.
- Requires `DASHSCOPE_API_KEY` (see `.env` / `agent/.env`).
- Depends on running microservices (`macrel`, `mic`, `hemolysis`, `cpp`,
  `structure`, ...).

---

### 2. Start the frontend (React + Vite)

```bash
cd <PROJECT_ROOT>/frontend
npm install        # first time only
npm run dev
```

Access URLs:
- Localhost: `http://localhost:3000`
- LAN: `http://<your-host-ip>:3000` (ensure firewall allows port 3000)

**Notes**:
- Vite supports hot module reloading.
- For production, run `npm run build` (artifacts appear under `dist/`).

---

### 3. Start the dependency services (optional)

For full functionality, launch every Docker microservice:

```bash
cd <PROJECT_ROOT>
docker compose up -d
```

Service list:

| Service | Port | Purpose |
|---------|------|---------|
| `backend` | 5000 | Flask API |
| `macrel` | 8000 | AMP prediction |
| `mic` | 8001 | MIC prediction |
| `hemolysis` | 8002 | Hemolysis prediction |
| `cpp` | 8003 | Cell-penetrating peptide prediction |
| `structure` | 8004 | 3D structure prediction (ESMFold) |

---

## 🔄 Restarting Services

### Restart backend
```bash
cd <PROJECT_ROOT>
docker compose restart backend
```

### Restart frontend
```bash
# Ctrl+C the current process, then:
cd <PROJECT_ROOT>/frontend
npm run dev
```

### Restart everything
```bash
cd <PROJECT_ROOT>
docker compose restart
```

---

## ⏹️ Stopping Services

### Stop backend only
```bash
cd <PROJECT_ROOT>
docker compose stop backend
```

### Stop the frontend
```bash
# In the frontend terminal: Ctrl+C
# Or, port-scoped kill:
lsof -ti:3000 | xargs kill -9 2>/dev/null
```

### Stop all Docker services
```bash
cd <PROJECT_ROOT>
docker compose stop
```

### Remove containers (non-destructive to volumes)
```bash
cd <PROJECT_ROOT>
docker compose down
# Containers are deleted, but named volumes are preserved.
```

### Full teardown including volumes (⚠️ destructive)
```bash
cd <PROJECT_ROOT>
docker compose down -v
# ⚠️ This DELETES all volumes, including the database!
```

---

## 🐛 Troubleshooting

### 1. Port already in use
```bash
# Identify the process holding the port
lsof -i:5000   # backend
lsof -i:3000   # frontend

# Kill it
kill <PID>
```

### 2. A Docker container failed to start
```bash
# Container status
docker ps -a

# Start a specific service
docker compose up -d <service_name>
```

### 3. Frontend cannot reach the backend
- Verify backend is up: `curl http://localhost:5000/api/health`
- CORS is enabled in the backend via `CORS(app)`; check that it is not
  overridden by a reverse proxy.
- Check host firewall rules.

### 4. The knowledge base fails to load
- **If `vector_store/` is missing or empty**: you forgot the first-time
  index build — run `python knowledge_builder/rebuild_index.py`
  (see the *First-time Setup* section above).
- Verify the `knowledge_builder` mount in `docker-compose.yml`.
- Verify the HuggingFace cache mount
  (`/home/<user>/.cache/huggingface:/root/.cache/huggingface`).
- Check the `sentence-transformers` version compatibility.

---

## 📝 Logs

### Backend logs
```bash
docker compose logs -f backend
```

### Frontend logs
Output appears directly in the terminal running `npm run dev`, and in the
browser Console.

### Container logs
```bash
docker logs <container_name>
```

---

## ⚙️ Tool Orchestrator

### What is the Tool Orchestrator?

The Tool Orchestrator is the **central scheduler** inside the AMP-Agent. It:

- ✅ **Starts / stops services on demand** — based on the task requirements.
- ✅ **Optimizes GPU resources** — prevents simultaneous OOMs from multiple
  GPU-heavy services.
- ✅ **Enforces mutual exclusion** — heavy generators (Diff-AMP / HydrAMP)
  cannot run concurrently.
- ✅ **Restores a lightweight default state** — after a task finishes.

### Default behaviour (zero configuration)

**No manual setup needed**; the orchestrator manages the following services
automatically:

| Service | Type | Strategy | Notes |
|---------|------|----------|-------|
| `amp-designer` | Base generator | **Always on** | Embedding model, fast boot |
| `amp-macrel` | AMP prediction | On-demand | Auto-started when invoked |
| `amp-mic` | MIC prediction | On-demand | GPU service (~8 GB VRAM) |
| `amp-hemolysis` | Toxicity prediction | On-demand | GPU service (~6 GB VRAM) |
| `amp-cpp` | CPP prediction | On-demand | GPU service (~6 GB VRAM) |
| `amp-structure` | Structure prediction | On-demand | ESMFold (~10 GB VRAM) |
| `amp-diff-amp` | Structure-guided generation | **Mutex** | Conflicts with HydrAMP |
| `amp-hydramp` | Helical-biased generation | **Mutex** | Conflicts with Diff-AMP |

### Manual service control (optional)

#### Option 1: Orchestrator API (recommended)

```python
from agent.tool_orchestrator import ToolOrchestrator

orchestrator = ToolOrchestrator()

# Start / stop a specific service
orchestrator.start_service("mic")
orchestrator.stop_service("hemolysis")

# Inspect the active tools
print(f"Active tools: {orchestrator.active_tools}")

# Reset to the lightweight default state (amp-designer + macrel only)
orchestrator.reset_to_default_state()
```

#### Option 2: Plain Docker commands

```bash
docker compose ps                        # status of all services
docker compose up -d amp-mic             # start one
docker compose stop amp-hemolysis        # stop one
docker compose restart amp-structure     # restart one
docker compose up -d amp-mic amp-hemolysis amp-cpp   # batch start
```

### Resource tuning (advanced)

Edit `docker-compose.yml` to adjust resource limits:

```yaml
services:
  amp-mic:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          memory: 8G   # Adjust VRAM/RAM limit
```

### FAQ

#### Q1: How do I confirm that a service is up?
```bash
docker ps | grep amp-mic
curl http://localhost:8001/health
```

#### Q2: Why does a service occasionally fail to start?
- **VRAM exhausted** — run `nvidia-smi` to check GPU usage.
- **Port conflict** — verify no stale instance is running.
- **Docker network issue** — run `docker network prune` to clean up.

#### Q3: How do I scale for concurrent users?
- Increase service replicas (`replicas:` in `docker-compose.yml`).
- Replace Docker Compose with Kubernetes (see the `k8s/` folder when provided).
- Enable a Redis cache layer to avoid recomputing identical requests.

---

## 🛠️ Development Mode

### Modify backend code
1. Edit files under `<PROJECT_ROOT>/backend/` or `<PROJECT_ROOT>/agent/`.
2. Restart the backend: `docker compose restart backend`.
3. Refresh the browser.

**Tip**: Python module changes sometimes require rebuilding the Docker image:
```bash
cd <PROJECT_ROOT>
docker compose build backend
docker compose up -d backend
```

### Backend troubleshooting

#### Issue 1: Backend fails to start
```bash
docker compose logs backend --tail 100   # inspect logs
docker ps -a | grep backend              # container status
lsof -i:5000                             # port usage
```

Common errors:
- `ModuleNotFoundError` → dependency missing; rebuild the image.
- `Connection refused` → a dependent service is not running; check
  `mic`/`hemolysis`/etc.
- `DASHSCOPE_API_KEY not set` → populate `.env` / `agent/.env`.

#### Issue 2: Agent responses contain garbled or mixed-language text
**Cause**: hard-coded strings inside the Agent code.

**Workaround**: the backend default is `language="en"`; ensure all
user-facing strings route through `self.texts` rather than literal strings.

#### Issue 3: Knowledge-base retrieval fails
```bash
# Check sentence-transformers
docker exec amp-backend pip show sentence-transformers

# Verify mounts
docker inspect amp-backend | grep -A 5 Mounts

# Smoke-test model loading
docker exec amp-backend python -c \
  "from sentence_transformers import SentenceTransformer; print('OK')"
```

### Modify frontend code
1. Edit files under `<PROJECT_ROOT>/frontend/src/`.
2. Vite hot-reloads automatically.
3. If the page does not refresh, hard reload with `Ctrl + Shift + R`.

### Safely restart the frontend (without disconnecting other Node tools)
```bash
# Port-scoped kill: only the Vite dev server on :3000 is terminated.
lsof -ti:3000 | xargs kill -9 2>/dev/null
cd <PROJECT_ROOT>/frontend
npm run dev
```

**⚠️ Warnings**:
- **Do NOT** use `pkill -f node` or `killall node` — they kill every Node
  process (IDEs, language servers, etc.).
- **Prefer** `lsof -ti:3000` to target a specific port only.

### Frontend troubleshooting

#### Issue 1: Page spinner never ends
1. Open the browser DevTools (F12).
2. **Console** tab — any JavaScript errors?
3. **Network** tab — any requests stuck in `pending` state?

Fix:
```bash
# 1. Is the backend healthy?
curl http://localhost:5000/api/health

# 2. Are there duplicate Vite processes?
ps aux | grep vite | grep -v grep

# 3. Clear the Vite cache and restart
rm -rf <PROJECT_ROOT>/frontend/node_modules/.vite
lsof -ti:3000 | xargs kill -9 2>/dev/null
cd <PROJECT_ROOT>/frontend && npm run dev
```

#### Issue 2: Text appears inside a chart iframe
**Cause**: the SSE stream handler appended a plain-text message to a
non-text message.

**Status**: fixed — the frontend now inspects the last message type and
starts a new message whenever the type (text / plotly / table) changes.

#### Issue 3: Charts are truncated or flattened
**Cause**: the chart container height is not constrained correctly.

**Fix**: fixed CSS height plus scrolling overflow:
```css
.plotly-grid .plotly-frame {
  width: 100%;
  max-width: 800px;
  height: 650px;
  overflow: auto;
}
```

---

## 🎯 One-shot Full Startup

```bash
# 1. Start all Docker services (⚠️ important: not just the backend!)
cd <PROJECT_ROOT>
docker compose up -d
# ↑ No argument = every microservice (designer / diff-amp / hydramp /
#   mic / hemolysis / ...). Generators can then switch with zero warm-up.

# 2. Verify service health
curl http://localhost:5000/api/health
docker compose ps

# 3. (Optional) List the services that Tool Orchestrator has auto-started
docker ps --filter "name=amp-"

# 4. Start the frontend in a new terminal
cd <PROJECT_ROOT>/frontend
npm run dev

# 5. Open http://localhost:3000 in your browser.
```

**Tip**: Tool Orchestrator auto-starts each service on first invocation — you
do **not** need to pre-warm every container. However, if you plan to switch
generators frequently (e.g., Diff-AMP ↔ HydrAMP), a one-time full boot
avoids the 10–15 s cold-start penalty on each switch.

---

## 📦 Production Deployment

### Build the frontend
```bash
cd <PROJECT_ROOT>/frontend
npm run build
# Artifacts appear under dist/
```

### Serve with Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root <PROJECT_ROOT>/frontend/dist;
        try_files $uri /index.html;
    }

    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🔗 Further Reading

- Architecture: [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) and
  `docs/architecture/PROJECT_ARCHITECTURE.md`
- Mathematical core: [`CORE_ALGORITHMS.md`](CORE_ALGORITHMS.md)
- API endpoints: hit `http://localhost:5000/api/health` to discover routes
- Frontend components: `frontend/src/components/`

---

**Maintainer**: AMP-Agent Team
**Version**: 3.0.1
