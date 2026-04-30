# Vibe Coding Platform - Technical Reference

This document describes the architecture, conventions, and available resources for building applications on the Vibe Coding platform. Every application is deployed to a dedicated GCP project provisioned via a standardized Terraform template.

**Important:** Not every application needs every resource. The GCP project comes pre-provisioned with a fixed set of resources, but your application should only use what it needs. A static dashboard doesn't need Firestore. A data API doesn't need a frontend. Use only what serves your feature.

## Architecture Overview

```
                    load balancing project (shared)
                ┌──────────────────────────────────────┐
                │                                      │
   User ──────>│  Global External Application LB      │
                │  (wildcard Google-managed SSL cert)   │
                │                                      │
                └──────────────┬───────────────────────┘
                               │
- - - - - - - - - - - - - - - -│- - - - - - - - - - - - - - - -
                               │
                    business project (per-app)
                ┌──────────────┴───────────────────────┐
                │                                      │
                │  Identity-Aware Proxy (IAP)          │
                │  ├── Azure AD (user auth)            │
                │  └── AD Group access control         │
                │                                      │
                │  Cloud Run (single container)        │
                │  ├── Port 8080                       │
                │  ├── /healthz (health check)         │
                │  ├── /api/* (backend routes)         │
                │  └── /* (frontend static files)      │
                │                                      │
                │  Service Account                     │
                │  ├── roles/datastore.user             │
                │  ├── roles/storage.objectUser         │
                │  └── roles/aiplatform.user            │
                │                                      │
                │  ┌─ Available Resources ────────────┐ │
                │  │  Firestore     (optional)        │ │
                │  │  Cloud Storage (optional)        │ │
                │  │  Vertex AI     (optional)        │ │
                │  └──────────────────────────────────┘ │
                │                                      │
                └──────────────────────────────────────┘
```

Two GCP projects are involved:
- **Load balancing project** (shared): Hosts the Global External Application Load Balancer with a wildcard Google-managed SSL certificate. Managed by the platform team. You never touch this.
- **Business project** (per-app): Your application runs here. Provisioned by the platform team via Terraform. Contains Cloud Run, the service account, and optionally Firestore and Cloud Storage.

## Project Inputs

When the platform team provisions your GCP project, you receive three values. These are the only project-specific inputs your application needs:

| Input | Example | Description |
|---|---|---|
| `GCP_PROJECT_ID` | `l-biz-myapp-prod` | Your GCP project ID. Used by all GCP client libraries. |
| `GCS_BUCKET` | `l-biz-myapp-prod-myapp-gcs` | Your Cloud Storage bucket name. Only needed if your app uses file storage. |
| `SA_NAME` | `myapp-sa@l-biz-myapp-prod.iam.gserviceaccount.com` | Your service account email. Used for local development via impersonation (see [Local Development](#local-development)). Not used in production. |

`GCP_PROJECT_ID` and `GCS_BUCKET` go into `container/config.env`, which is copied into the container and read by the application at startup. `SA_NAME` is only used locally for `gcloud` impersonation and is never in the container.

## Application Archetypes

Your app will fall into one of these patterns. Choose the simplest one that fits.

### Full-Stack App (Frontend + Backend)
Python FastAPI backend serving a React SPA. Use when your app has both a UI and server-side logic, API routes, or GCP resource access.

### Backend-Only API
Python FastAPI without a frontend. Use when you're building a service or API that other systems consume. The health check endpoint is still required.

### Static Frontend
React SPA with no backend logic. The app is built and served as static files by a minimal Python server (or a simple file server). Use when your app is purely client-side (e.g., a dashboard consuming external APIs). The health check endpoint is still required — use a minimal FastAPI or HTTP server to serve static files and expose `/healthz`.

## Hard Rules

These are non-negotiable. If your app violates any of these, it will not deploy.

### 1. Source Files in `/container`

All application source code, the Dockerfile, and docker-compose.yml MUST live inside the `/container` folder in the repository root. This is required by the CI/CD pipeline.

```
your-repo/
├── CLAUDE.md
├── container/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── config.env
│   ├── docker-compose.yml
│   ├── backend/
│   └── frontend/
├── specs/
└── ...
```

### 2. Single Container Image

The application MUST be a single Docker image that serves everything: frontend static assets and backend API. No sidecar containers, no separate frontend deployment, no CDN.

### 3. Non-Root User

The container MUST run as a non-root user. Create a dedicated user in the Dockerfile and switch to it before the CMD instruction.

### 4. Port 8080

The container MUST listen on port `8080`. This is the Cloud Run ingress port configured by the platform.

### 5. Health Check at `/healthz`

The application MUST expose `GET /healthz` returning HTTP 200 with `{"status": "ok"}`. This endpoint MUST NOT require authentication. Cloud Run uses it for startup and liveness probes.

### 6. Configuration via `config.env`

Project-specific configuration (`GCP_PROJECT_ID`, `GCS_BUCKET`) MUST be defined in `container/config.env`. This file is copied into the container image and read by the application at startup via `pydantic-settings`. Any additional environment variables the application needs should also be added to this file.

### 7. No Secrets in Code or Environment

The application MUST NOT contain secrets (API keys, tokens, passwords) in source code, environment variables, or the container image. All authentication to GCP services uses Application Default Credentials (ADC). On Cloud Run, the attached service account provides credentials automatically. For local development, use service account impersonation via `gcloud` (see [Local Development](#local-development)). If the application needs to store user-provided secrets, encrypt them and store them in Firestore.

### 8. IAP Authentication via Headers

If the application needs to identify users, it MUST read identity from the IAP header `X-Goog-Authenticated-User-Email`. Do NOT implement your own login page, OAuth flow, or JWT verification. IAP handles all of this.

## Tech Stack

### Required (all apps)

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Runtime language |
| Pydantic | 2.x | Data validation and settings |
| Docker | Multi-stage build | Containerization |

### Backend (when your app has server-side logic)

| Technology | Version | Purpose |
|---|---|---|
| FastAPI | 0.115+ | Web framework |
| Uvicorn | latest | ASGI server |
| pydantic-settings | 2.x | Environment variable management |

### Frontend (when your app has a UI)

| Technology | Version | Purpose |
|---|---|---|
| React | 19.x | UI framework |
| TypeScript | 5.x | Type-safe JavaScript |
| Vite | 6.x | Build tool and dev server |
| Tailwind CSS | 3.x | Utility-first CSS |
| React Router | v7 | Client-side routing |

### GCP Client Libraries (use only what you need)

| Library | Purpose |
|---|---|
| `google-cloud-firestore` | Firestore database access |
| `google-cloud-storage` | Cloud Storage file operations |
| `google-cloud-aiplatform` | Vertex AI / Gemini API access |

## GCP Resources Reference

These resources are pre-provisioned in your GCP project. Use only what your application requires.

### Cloud Run (always used)

Your app runs here. Configuration is managed by the platform team via Terraform.

| Setting | Value |
|---|---|
| Min instances | 0 |
| Max instances | 2 |
| CPU | 1 |
| Memory | 2 GB |
| Port | 8080 |
| Concurrency | 80 |
| Request timeout | 300s |
| Scaling | Automatic, scale-to-zero |
| Ingress | Internal + Cloud Load Balancing |

### Service Account (always available)

A dedicated service account is attached to your Cloud Run service with these roles:

| Role | Access |
|---|---|
| `roles/datastore.user` | Firestore read/write |
| `roles/storage.objectUser` | Cloud Storage read/write/delete |
| `roles/aiplatform.user` | Vertex AI / Gemini API |
| `roles/run.invoker` | Invoke other Cloud Run services |

The service account email (`SA_NAME`) is provided by the platform team. You use it for local development by impersonating it via `gcloud` — no key files are needed. See [Local Development](#local-development).

### Firestore (optional)

Serverless NoSQL document database. Use when your app needs to persist structured data.

- Uses the `(default)` database in the project.
- No schema migrations needed — Firestore is schemaless.
- Collections are top-level. Use subcollections only for clear parent-child relationships.
- Document IDs: auto-generated for user content, meaningful IDs (e.g., email) for lookup patterns.
- Daily backups with 30-day retention are configured automatically.

**When to use:** User data, app state, configuration, content management.
**When NOT to use:** Large binary files (use Cloud Storage), analytics/time-series data.

### Cloud Storage (optional)

Object storage for files. Use when your app handles file uploads or needs to store/serve binary content.

- Bucket name is defined in `config.env` as `GCS_BUCKET`.
- Use logical folder structure in blob names (e.g., `uploads/{user_id}/{timestamp}-{filename}`).
- Public URL format: `https://storage.googleapis.com/{bucket}/{blob_name}`

**When to use:** File uploads, images, documents, exports.
**When NOT to use:** Structured data (use Firestore).

### Vertex AI (optional)

Access to Google's AI models (Gemini). Use when your app needs LLM/GenAI capabilities.

- Access via the `google-cloud-aiplatform` Python client.
- Uses ADC — no API keys needed.

**When to use:** Text generation, summarization, classification, embeddings.

## Configuration

### `config.env`

The file `container/config.env` holds all project-specific configuration. It is copied into the container image and loaded by the application at startup. This file is committed to the repository — it contains no secrets, only project identifiers.

```env
GCP_PROJECT_ID=your-gcp-project-id
GCS_BUCKET=your-gcp-project-id-your-app-gcs
```

The platform team provides the values for `GCP_PROJECT_ID` and `GCS_BUCKET`. Fill them in once when you set up the project. If your application needs additional configuration, add it here.

### Config Pattern (Pydantic Settings)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gcp_project_id: str
    gcs_bucket: str = ""

    model_config = {"env_file": "config.env", "extra": "ignore"}

settings = Settings()
```

Key rules:
- `pydantic-settings` loads `config.env` automatically. The same file works in the container and in local development.
- All GCP authentication uses Application Default Credentials. No credential files, no key paths, no conditional logic.
- Validate required variables at startup. The app must crash immediately with a clear error if required vars are missing.

## Dockerfile

Use a multi-stage build. The container MUST run as a non-root user. `config.env` is copied into the image.

### Full-Stack App

```dockerfile
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend. We must use registry.alza.cz/ as the download proxy.
FROM registry.alza.cz/python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./static/
COPY config.env ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Backend-Only API

```dockerfile
FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY config.env ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Static Frontend (minimal server)

```dockerfile
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn

COPY backend/main.py ./
COPY --from=frontend-build /app/frontend/dist ./static/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

For a static frontend, the `backend/main.py` is minimal — just `/healthz` and the static file mount. No `config.env` is needed since there are no GCP resources to connect to.

### .dockerignore

Always include a `.dockerignore` in the `/container` folder:

```
.git/
node_modules/
__pycache__/
*.pyc
specs/
docs/
.specify/
*.md
.dockerignore
Dockerfile
docker-compose.yml
.vscode/
.idea/
.DS_Store
```

## Project Structure

### Full-Stack App

```
your-repo/
├── CLAUDE.md                  # Project context for AI agent
├── principles.md              # Coding guidelines (speckit constitution input)
├── tech.md                    # This file (speckit plan input)
│
├── container/
│   ├── Dockerfile             # Multi-stage build
│   ├── .dockerignore
│   ├── config.env             # Project configuration (GCP_PROJECT_ID, GCS_BUCKET)
│   ├── docker-compose.yml     # Local dev (optional)
│   │
│   ├── backend/
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py        # FastAPI app, /healthz, static mount
│   │       ├── config.py      # Pydantic Settings (loads config.env)
│   │       ├── auth.py        # IAP header extraction
│   │       ├── dependencies.py # GCP client initialization (ADC)
│   │       ├── routers/       # API route handlers
│   │       ├── models/        # Pydantic models
│   │       └── services/      # Business logic, GCP service clients
│   │
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts     # Dev proxy: /api -> backend
│       └── src/               # React app
│
├── .specify/                  # Speckit configuration
└── specs/                     # Feature specifications
```

### Backend-Only API

```
your-repo/
├── CLAUDE.md
├── principles.md
├── tech.md
│
├── container/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── config.env
│   ├── backend/
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── routers/
│   │       ├── models/
│   │       └── services/
│
├── .specify/
└── specs/
```

### Static Frontend

```
your-repo/
├── CLAUDE.md
├── principles.md
├── tech.md
│
├── container/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── backend/
│   │   └── main.py            # Minimal: /healthz + static mount only
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       └── src/
│
├── .specify/
└── specs/
```

## GCP Client Initialization

GCP clients use Application Default Credentials everywhere — both on Cloud Run and in local development (via service account impersonation). No conditional logic is needed.

```python
from google.cloud import firestore
from app.config import settings

def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=settings.gcp_project_id)
```

The same pattern applies to `storage.Client` and Vertex AI clients. ADC handles credentials automatically:
- **On Cloud Run**: The attached service account provides credentials.
- **Local dev**: `gcloud` impersonation provides credentials (see [Local Development](#local-development)).

## Authentication (IAP)

### How It Works

1. User navigates to the app URL.
2. The Global External Load Balancer routes the request to IAP.
3. IAP checks if the user is authenticated and belongs to the designated Azure AD group.
4. If authorized, IAP forwards the request to Cloud Run with the header `X-Goog-Authenticated-User-Email`.
5. Your app reads this header to identify the user.

### Auth Pattern

```python
from fastapi import Request, HTTPException

async def get_current_user(request: Request) -> UserInfo:
    raw_email = request.headers.get("X-Goog-Authenticated-User-Email", "")
    # Header format: "accounts.google.com:user@example.com"
    email = raw_email.split(":", 1)[-1] if ":" in raw_email else raw_email

    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    name = email.split("@")[0]
    return UserInfo(email=email, name=name)
```

Key rules:
- Do NOT verify the IAP JWT token. IAP handles verification. Cloud Run ingress only accepts traffic through the load balancer.
- Do NOT implement login pages, OAuth flows, or session management.
- For local development, mock the IAP header by sending `X-Goog-Authenticated-User-Email` in your requests (e.g., via the Vite proxy config, a browser extension, or tools like `curl -H "X-Goog-Authenticated-User-Email: accounts.google.com:you@alza.cz"`).

### Admin Authorization (Optional)

If your app needs admin roles, use a Firestore `admins` collection where each document ID is the user's email. If the document exists, the user is an admin.

**Auto-admin for first user:** If the `admins` collection is empty (no admins exist yet), the first user who accesses the app should be automatically added as an admin. This ensures the app is usable immediately after deployment without manual Firestore seeding.

```python
db = get_firestore_client()

async def check_admin(email: str) -> bool:
    admin_doc = db.collection("admins").document(email).get()
    if admin_doc.exists:
        return True

    # If no admins exist yet, make this user the first admin
    admins = db.collection("admins").limit(1).get()
    if len(admins) == 0:
        db.collection("admins").document(email).set({"auto_created": True})
        return True

    return False
```

## FastAPI App Structure

### main.py Pattern

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Your App Name")

# CORS only needed in dev (separate frontend dev server)
if os.getenv("CORS_ALLOWED_ORIGIN"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("CORS_ALLOWED_ORIGIN")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Health check - MUST be before static mount, MUST be unauthenticated
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

# Your API routes
app.include_router(your_router, prefix="/api")

# Static files mount MUST be last (catch-all for frontend SPA routing)
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
```

Critical ordering:
1. Middleware (CORS) — first
2. `/healthz` route — before static mount
3. `/api/*` routes — before static mount
4. `StaticFiles` mount on `/` — **LAST** (it's a catch-all; `html=True` enables SPA routing)

### Frontend Vite Config

In local dev, the frontend proxies API calls to the backend. Add a mock IAP header so the backend receives a user identity:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        headers: {
          'X-Goog-Authenticated-User-Email': 'accounts.google.com:dev@alza.cz',
        },
      },
    },
  },
});
```

Always use relative paths for API calls:

```typescript
// Correct — works in both dev (proxy) and prod (same origin)
fetch('/api/entries')

// Wrong — breaks in production
fetch('http://localhost:8000/api/entries')
```

## CI/CD

Deployment is fully automated. You do not need to configure anything.

- **Feature branches** (`feature/*`): Pushing to any branch starting with `feature/` triggers a build and deploy to your Cloud Run service.
- **Develop branch**: Merging into `develop` triggers a build and deploy.
- The CI/CD pipeline builds the Docker image from `/container/Dockerfile`, pushes it to an external Artifact Registry, and deploys it to Cloud Run.

You do not manage the Artifact Registry, Cloud Build, or deployment scripts. Just push code.

**Branch naming:** All work branches MUST follow the `feature/<name>` pattern (e.g., `feature/001-invoice-manager`). Only branches matching `feature/*` trigger CI/CD. If speckit or any script creates a branch with a different naming convention, rename it to `feature/<name>` before pushing.

## Local Development

### Prerequisites

You must have `gcloud` CLI installed and be authenticated:

```bash
gcloud auth login
```

### Setup

The platform team provides three values for your project: `GCP_PROJECT_ID`, `GCS_BUCKET`, and `SA_NAME` (service account email).

1. **Fill in `config.env`.** Open `container/config.env` and set `GCP_PROJECT_ID` and `GCS_BUCKET` with the values provided by the platform team. This file is committed to the repository and used both locally and in the container.

2. **Impersonate the service account.** This gives your local `gcloud` session the same permissions as the Cloud Run service, without downloading any key files:

```bash
gcloud auth application-default login --impersonate-service-account=SA_NAME
```

Replace `SA_NAME` with the service account email provided by the platform team (e.g., `myapp-sa@l-biz-myapp-prod.iam.gserviceaccount.com`).

3. **Start backend:**

```bash
cd container/backend && uvicorn app.main:app --reload --port 8000
```

4. **Start frontend:**

```bash
cd container/frontend && npm run dev
```

5. **Open** `http://localhost:5173` — the Vite proxy sends a mock IAP header to the backend automatically.

### Testing the Container Locally

```bash
cd container

docker build -t your-app .

docker run -p 8080:8080 your-app

# Verify
curl http://localhost:8080/healthz
curl -H "X-Goog-Authenticated-User-Email: accounts.google.com:dev@alza.cz" \
     http://localhost:8080/api/your-endpoint
open http://localhost:8080
```

Note: `GCP_PROJECT_ID` and `GCS_BUCKET` are loaded from `config.env` inside the image. GCP API calls will fail in the container locally (no ADC credentials) — this is expected. The container test verifies the app starts, serves the frontend, and responds to health checks.

## Deployment Checklist

Before pushing to a `feature/*` branch:

- [ ] All source files are inside `/container`
- [ ] Single Dockerfile produces one image with everything the app needs
- [ ] Container runs as a non-root user
- [ ] Container listens on port 8080
- [ ] `config.env` contains correct `GCP_PROJECT_ID` and `GCS_BUCKET`
- [ ] `GET /healthz` returns 200 OK without authentication
- [ ] GCP clients use ADC (no key files, no credential paths in code)
- [ ] No secrets in source code, environment variables, or the container image
- [ ] User identity is read from `X-Goog-Authenticated-User-Email` header (if needed)
- [ ] No login page, OAuth flow, or JWT verification implemented
- [ ] API routes use `/api/*` prefix
- [ ] Frontend uses relative paths for API calls (`/api/...`)
- [ ] `StaticFiles` mount is registered last in the FastAPI app
- [ ] No service account key files are committed to the repository