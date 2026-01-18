# Brevi - URL Shortener Implementation Plan

## Overview

A URL shortener with analytics, focused on learning modern software engineering practices.

---

## Recommended Technology Stack

### Backend (Python)

| Component | Recommendation | Why |
|-----------|---------------|-----|
| Package Manager | **uv** | Extremely fast, pip-compatible, modern |
| Framework | **FastAPI** | Async, automatic OpenAPI docs, excellent for REST APIs, great DX |
| ORM | **SQLAlchemy 2.0** | Industry standard, async support, type hints |
| Validation | **Pydantic** | Built into FastAPI, great for request/response models |
| Database | **PostgreSQL** | Robust, great for analytics queries, JSON support |
| Caching | **Redis** | Perfect for high-volume redirect lookups |
| Auth | **Authlib** | OAuth handling for GitHub/Google |
| Message Queue | **Redis Pub/Sub** | Event-driven communication between services |

### Frontend (React)

| Component | Recommendation | Why |
|-----------|---------------|-----|
| Package Manager | **pnpm** | Fast, disk-efficient, strict |
| Build Tool | **Vite** | Fast, modern, excellent DX |
| Language | **JavaScript** | Simpler setup, faster iteration |
| Data Fetching | **TanStack Query** | Caching, loading states, mutations |
| Routing | **React Router v6** | Standard, feature-rich |
| Styling | **Tailwind CSS** | Utility-first, rapid prototyping |
| Forms | **React Hook Form** | Performance, validation |
| Components | **shadcn/ui** | Beautiful, accessible, customizable |
| Charts | **Chart.js + react-chartjs-2** | Popular, many chart types, good docs |

### Infrastructure & DevOps

| Component | Recommendation | Why |
|-----------|---------------|-----|
| Containerization | **Docker** | Consistent environments |
| Orchestration | **Kubernetes** | Industry standard, learn pods, services, ingress, scaling |
| Local K8s | **Docker Desktop** | Built-in K8s on Windows, easiest setup |
| IaC | **Pulumi (Python)** | Uses Python (matches backend), can also provision K8s resources |
| CI/CD | **GitHub Actions** | Native to GitHub, free tier generous |
| Hosting | **TBD** | GKE/EKS/AKS or simpler (Railway/Fly.io) |

### Testing

| Layer | Tool |
|-------|------|
| Backend Unit | pytest |
| Backend Integration | pytest + testcontainers |
| Frontend Unit | Vitest |
| E2E | Playwright |

### Observability

| Component | Tool | Why |
|-----------|------|-----|
| Structured Logging | **structlog** (Python) | JSON logs, context propagation, async-friendly |
| Metrics | **Prometheus** | Industry standard, great with Grafana |
| Dashboards | **Grafana** | Visualize metrics, create alerts |
| Distributed Tracing | **OpenTelemetry** | Trace requests across services, vendor-neutral |
| Error Tracking | **Sentry** | Catch exceptions, stack traces, release tracking |

### Security

| Component | Tool/Approach | Why |
|-----------|---------------|-----|
| Rate Limiting | **slowapi** (FastAPI) | Protect endpoints from abuse |
| CORS | FastAPI CORSMiddleware | Control allowed origins |
| Security Headers | Custom middleware | XSS, clickjacking, content-type protection |
| Secrets | **.env files + docker secrets** | Never commit secrets, 12-factor app |
| Input Validation | Pydantic + URL validation | Prevent injection, validate URLs |

### Developer Experience

| Component | Tool | Why |
|-----------|------|-----|
| Python Linting | **Ruff** | Extremely fast, replaces flake8/isort/black |
| Python Types | **mypy** | Static type checking |
| JS/TS Linting | **ESLint + Prettier** | Consistent code style |
| Pre-commit | **pre-commit** | Run checks before every commit |
| Task Runner | **Makefile** or **just** | Common commands: `make dev`, `make test` |
| Local HTTPS | **mkcert** | Required for OAuth callbacks locally |

---

## Project Structure

```
brevy/
├── services/
│   ├── api/                    # Main API service
│   │   ├── app/
│   │   │   ├── api/           # Route handlers
│   │   │   ├── core/          # Config, security, dependencies
│   │   │   ├── models/        # SQLAlchemy models
│   │   │   ├── schemas/       # Pydantic schemas
│   │   │   ├── services/      # Business logic
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic/           # DB migrations
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   │
│   └── analytics/              # Analytics service (separate)
│       ├── app/
│       │   ├── consumers/     # Redis Pub/Sub consumers
│       │   ├── models/        # Analytics-specific models
│       │   ├── aggregators/   # Data aggregation logic
│       │   └── main.py
│       ├── tests/
│       ├── pyproject.toml
│       └── Dockerfile
│
├── packages/
│   └── shared/                 # Shared Python code (schemas, utils)
│       └── pyproject.toml
│
├── client/                     # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/               # API client
│   │   └── main.jsx
│   ├── tests/
│   ├── package.json
│   └── Dockerfile
│
├── infra/                      # Pulumi IaC
│   └── __main__.py
│
├── k8s/                        # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── api-deployment.yaml
│   ├── api-service.yaml
│   ├── analytics-deployment.yaml
│   ├── analytics-service.yaml
│   ├── client-deployment.yaml
│   ├── client-service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml
│
├── charts/                     # Helm charts (optional)
│   └── brevi/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-prod.yaml
│       └── templates/
│
├── docker-compose.yml          # Local dev environment (Phase 1-5)
├── .github/workflows/          # CI/CD
└── README.md
```

---

## Architecture Overview

```
                                    ┌─────────────────┐
                                    │  React Client   │
                                    └────────┬────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Service (FastAPI)                          │
│  • Short link CRUD                                                          │
│  • Redirect handling                                                        │
│  • OAuth authentication                                                     │
│  • Publishes click events                                                   │
└──────────┬─────────────────────────────────┬───────────────────────────────┘
           │                                 │
           │                                 │ publish "click" events
           ▼                                 ▼
    ┌─────────────┐                  ┌─────────────┐
    │  PostgreSQL │                  │    Redis    │◀──────────────┐
    │  (links +   │                  │  (cache +   │               │
    │   users)    │                  │  pub/sub)   │               │
    └─────────────┘                  └──────┬──────┘               │
                                            │ subscribe            │
                                            ▼                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Analytics Service (FastAPI)                         │
│  • Consumes click events from Redis                                         │
│  • Stores raw click data                                                    │
│  • Aggregates statistics (hourly, daily)                                    │
│  • Exposes analytics API endpoints                                          │
└──────────┬──────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────┐
    │  PostgreSQL │
    │ (analytics) │
    └─────────────┘
```

**Flow for redirect (performance critical):**

1. User hits `brevi.io/abc123`
2. Redis lookup first (cache hit → instant redirect)
3. Cache miss → PostgreSQL lookup → cache result → redirect
4. Publish click event to Redis (non-blocking)
5. Analytics service consumes event asynchronously

**Benefits of separate analytics service:**

- Redirect latency not affected by analytics processing
- Can scale analytics independently
- Clear separation of concerns
- Great learning opportunity for microservices patterns

**Data flow for analytics requests:**

1. Frontend requests analytics from API service (`GET /api/v1/links/{id}/analytics`)
2. API service forwards/proxies to Analytics service internally
3. This keeps auth centralized in API service and simplifies frontend CORS

**Authentication:**

- Uses httpOnly cookies (secure, automatic with requests)
- API service handles OAuth flow and sets cookies
- Cookies sent automatically with all API requests

---

## Implementation Phases

### Phase 1: Project Scaffolding & Developer Experience

**1.1 Folder Structure**

- [x] Create `services/api/` directory
- [x] Create `services/analytics/` directory
- [x] Create `packages/shared/` directory
- [x] Create `client/` directory
- [x] Create `infra/` directory
- [x] Remove existing venv from root (none existed)

**1.2 API Service Setup**

- [x] Initialize with `uv init` in services/api/
- [x] Configure pyproject.toml (dependencies, scripts)
- [x] Set up Ruff configuration (in pyproject.toml)
- [x] Set up mypy configuration (in pyproject.toml)
- [x] Create basic FastAPI app structure (main.py, routers, etc.)

**1.3 Analytics Service Setup**

- [x] Initialize with `uv init` in services/analytics/
- [x] Configure pyproject.toml
- [x] Set up Ruff + mypy configuration (in pyproject.toml)
- [x] Create basic FastAPI app structure

**1.4 Shared Package Setup**

- [x] Initialize shared package with uv
- [x] Create shared Pydantic schemas (ClickEvent, etc.)
- [x] Configure as local dependency for both services

**1.5 React Client Setup**

- [x] Initialize with `pnpm create vite` (React + JavaScript)
- [x] Install core dependencies (TanStack Query, React Router, Tailwind)
- [x] Configure ESLint + Prettier
- [x] Set up project structure (pages/, components/, hooks/, api/)
- [x] Initialize shadcn/ui

**1.6 Docker & Local Development**

- [x] Create docker-compose.yml with PostgreSQL, Redis
- [x] Create .env.example with required variables
- [x] Create .env (gitignored) with local values
- [x] Add health checks for containers
- [x] Create volumes for data persistence

**1.7 Developer Experience**

- [x] Create Makefile with common commands
- [x] Set up pre-commit hooks (ruff, mypy, eslint, prettier)
- [x] Install mkcert and generate local HTTPS certificates
- [x] Create README with setup instructions

---

### Phase 2: Core API Service

**2.1 Database Setup**

- [ ] Configure SQLAlchemy 2.0 with async support
- [ ] Set up Alembic for migrations
- [ ] Create database connection pool
- [ ] Create `api` schema in PostgreSQL

**2.2 User Model & Auth Foundation**

- [ ] Create User SQLAlchemy model
- [ ] Create User Pydantic schemas (UserCreate, UserResponse)
- [ ] Set up session/JWT token handling
- [ ] Create auth middleware for protected routes

**2.3 OAuth Implementation**

- [ ] Register GitHub OAuth application
- [ ] Register Google OAuth application
- [ ] Implement `/api/v1/auth/github` login redirect
- [ ] Implement `/api/v1/auth/github/callback` handler
- [ ] Implement `/api/v1/auth/google` login redirect
- [ ] Implement `/api/v1/auth/google/callback` handler
- [ ] Implement `/api/v1/auth/logout` endpoint
- [ ] Implement `/api/v1/auth/me` (get current user)

**2.4 Link Model & CRUD**

- [ ] Create Link SQLAlchemy model
- [ ] Create Link Pydantic schemas
- [ ] Implement `POST /api/v1/links` - create short link
- [ ] Implement `GET /api/v1/links` - list user's links (paginated)
- [ ] Implement `GET /api/v1/links/{id}` - get single link
- [ ] Implement `PATCH /api/v1/links/{id}` - update link
- [ ] Implement `DELETE /api/v1/links/{id}` - soft delete link
- [ ] Implement `GET /api/v1/links/{id}/analytics` - proxy to analytics service
- [ ] Add URL validation (valid URL format, not blocked domain)

**2.5 Short Code Generation**

- [ ] Implement random short code generator (base62, 6-8 chars)
- [ ] Implement custom slug validation (allowed chars, length, uniqueness)
- [ ] Handle collision detection and retry

**2.6 Redirect Endpoint**

- [ ] Implement `GET /{short_code}` redirect
- [ ] Add Redis caching for lookups
- [ ] Handle cache miss → DB lookup → cache set
- [ ] Handle expired links (return 410 Gone)
- [ ] Handle inactive links (return 404)
- [ ] Implement cache invalidation on link update/delete

**2.7 Click Event Publishing**

- [ ] Set up Redis Pub/Sub publisher
- [ ] Publish click event on every redirect (async, non-blocking)
- [ ] Include: link_id, timestamp, referrer, user_agent, IP

**2.8 Security & Rate Limiting**

- [ ] Configure CORS middleware (allowed origins)
- [ ] Add security headers middleware
- [ ] Implement rate limiting with slowapi
- [ ] Rate limit: redirect endpoint (high limit)
- [ ] Rate limit: create link endpoint (lower limit)

**2.9 Observability - API Service**

- [ ] Set up structlog for JSON logging
- [ ] Add request ID middleware (trace requests)
- [ ] Set up OpenTelemetry tracing
- [ ] Add Prometheus metrics endpoint
- [ ] Integrate Sentry for error tracking

---

### Phase 3: Analytics Service

**3.1 Service Foundation**

- [ ] Configure SQLAlchemy for analytics schema
- [ ] Set up Alembic migrations (separate from API)
- [ ] Create `analytics` schema in PostgreSQL

**3.2 Click Event Consumer**

- [ ] Implement Redis Pub/Sub subscriber
- [ ] Parse incoming click events
- [ ] Handle malformed events gracefully

**3.3 Click Storage**

- [ ] Create Click SQLAlchemy model
- [ ] Implement IP → Country/City lookup (GeoIP2 or IP-API)
- [ ] Store raw click events
- [ ] Add batch insert for high throughput

**3.4 Aggregation Jobs**

- [ ] Implement hourly aggregation logic
- [ ] Implement daily aggregation logic
- [ ] Calculate unique visitors (approximate, IP-based)
- [ ] Aggregate top referrers, top countries
- [ ] Schedule aggregation (cron or background task)

**3.5 Analytics API Endpoints**

- [ ] Implement `GET /analytics/{link_id}/summary` - totals
- [ ] Implement `GET /analytics/{link_id}/timeseries` - clicks over time
- [ ] Implement `GET /analytics/{link_id}/referrers` - top referrers
- [ ] Implement `GET /analytics/{link_id}/countries` - geographic data
- [ ] Add date range filtering

**3.6 Observability - Analytics Service**

- [ ] Set up structlog logging
- [ ] Add OpenTelemetry tracing
- [ ] Add Prometheus metrics (events processed, latency)
- [ ] Integrate Sentry

---

### Phase 4: Frontend

**4.1 Auth Flow**

- [ ] Create AuthContext for global auth state
- [ ] Implement login page with GitHub/Google buttons
- [ ] Handle OAuth callback redirect
- [ ] Store auth token (httpOnly cookie or localStorage)
- [ ] Implement logout functionality
- [ ] Create ProtectedRoute component

**4.2 API Client Setup**

- [ ] Set up Axios or fetch wrapper
- [ ] Configure TanStack Query client
- [ ] Create API hooks (useLinks, useCreateLink, useAnalytics)
- [ ] Handle auth token in requests
- [ ] Implement error handling

**4.3 Dashboard Page**

- [ ] Create dashboard layout
- [ ] Display list of user's links
- [ ] Show basic stats per link (total clicks)
- [ ] Implement pagination or infinite scroll
- [ ] Add search/filter functionality

**4.4 Create Link Page/Modal**

- [ ] Create link creation form
- [ ] URL input with validation
- [ ] Optional custom slug input
- [ ] Optional expiration date picker
- [ ] Show generated short URL after creation
- [ ] Copy to clipboard functionality

**4.5 Link Detail Page**

- [ ] Display link information
- [ ] Show analytics summary (total clicks, unique visitors)
- [ ] Implement time-series chart (clicks over time)
- [ ] Show top referrers list
- [ ] Show geographic breakdown (countries)
- [ ] Add date range selector

**4.6 Polish & UX**

- [ ] Add loading skeletons
- [ ] Implement error boundaries
- [ ] Add toast notifications
- [ ] Responsive design (mobile-friendly)
- [ ] Dark mode support (optional)

---

### Phase 5: DevOps & Testing

**5.1 Dockerfiles**

- [ ] Create Dockerfile for API service (multi-stage build)
- [ ] Create Dockerfile for Analytics service
- [ ] Create Dockerfile for React client (nginx for static files)
- [ ] Optimize image sizes

**5.2 CI Pipeline (GitHub Actions)**

- [ ] Lint job: Run Ruff, mypy, ESLint
- [ ] Test job: Run pytest, Vitest
- [ ] Build job: Build Docker images
- [ ] Add caching for dependencies (uv, pnpm)

**5.3 Backend Testing**

- [ ] Unit tests for short code generation
- [ ] Unit tests for URL validation
- [ ] Integration tests for CRUD endpoints (testcontainers)
- [ ] Integration tests for OAuth flow (mocked)
- [ ] Integration tests for Redis caching

**5.4 Frontend Testing**

- [ ] Unit tests for utility functions
- [ ] Component tests for key components
- [ ] Mock API responses for tests

**5.5 E2E Testing (Playwright)**

- [ ] Test: User can log in with GitHub
- [ ] Test: User can create a short link
- [ ] Test: User can view dashboard
- [ ] Test: Short link redirects correctly
- [ ] Test: Analytics page shows data

---

### Phase 6: Infrastructure, Kubernetes & Production

**6.1 Local Kubernetes Setup**

- [ ] Enable Kubernetes in Docker Desktop
- [ ] Verify `kubectl` works locally
- [ ] Install `kubectl` CLI and configure context
- [ ] Install Lens or k9s for K8s dashboard (optional)

**6.2 Kubernetes Manifests - Core**

- [ ] Create `k8s/` directory in project root
- [ ] Create Namespace manifest (`brevi` namespace)
- [ ] Create ConfigMap for non-sensitive config
- [ ] Create Secret for database credentials, Redis, OAuth secrets
- [ ] Create PersistentVolumeClaim for PostgreSQL (local dev)

**6.3 Kubernetes Manifests - Services**

- [ ] Create Deployment for API service
- [ ] Create Deployment for Analytics service
- [ ] Create Deployment for React client (nginx)
- [ ] Create Deployment for PostgreSQL (dev only, use managed in prod)
- [ ] Create Deployment for Redis (dev only, use managed in prod)
- [ ] Create Service (ClusterIP) for each deployment
- [ ] Add liveness and readiness probes to all deployments

**6.4 Kubernetes Manifests - Networking**

- [ ] Install NGINX Ingress Controller
- [ ] Create Ingress resource for routing
- [ ] Configure TLS with cert-manager (or manual certs)
- [ ] Route `/` to frontend, `/api/*` to API service, `/analytics/*` to Analytics service

**6.5 Kubernetes Manifests - Scaling & Resources**

- [ ] Add resource requests and limits to all pods
- [ ] Create HorizontalPodAutoscaler for API service (scale on CPU/requests)
- [ ] Create HorizontalPodAutoscaler for Analytics service

**6.6 Helm Charts (Optional but Recommended)**

- [ ] Initialize Helm chart structure (`helm create brevi`)
- [ ] Convert manifests to Helm templates
- [ ] Create values.yaml for environment-specific config
- [ ] Create values-dev.yaml and values-prod.yaml

**6.7 Pulumi Configuration**

- [ ] Set up Pulumi project (Python)
- [ ] Define managed PostgreSQL resource (cloud provider)
- [ ] Define managed Redis resource (cloud provider)
- [ ] Define Kubernetes cluster (GKE/EKS/AKS)
- [ ] Configure networking (VPC, security groups)
- [ ] Set up secrets management (cloud provider secrets)

**6.8 Monitoring Infrastructure**

- [ ] Deploy Prometheus to K8s (or use managed)
- [ ] Deploy Grafana to K8s (or use managed)
- [ ] Create dashboard: Redirect latency
- [ ] Create dashboard: Error rates
- [ ] Create dashboard: Popular links
- [ ] Create dashboard: Pod metrics (CPU, memory, restarts)
- [ ] Set up alerting rules

**6.9 Production Deployment**

- [ ] Provision cloud Kubernetes cluster with Pulumi
- [ ] Deploy K8s manifests/Helm chart to production cluster
- [ ] Configure production Ingress with real domain
- [ ] Set up SSL/TLS with cert-manager + Let's Encrypt
- [ ] Configure CDN for static assets (optional)
- [ ] Run smoke tests
- [ ] Verify HPA scales correctly under load

**6.10 Preview Environments (Bonus)**

- [ ] GitHub Action to deploy PR to preview namespace
- [ ] Create ephemeral namespace per PR
- [ ] Ephemeral database for previews
- [ ] Auto-cleanup namespace on PR close

---

## Decisions Made

| Category | Decision | Choice |
|----------|----------|--------|
| **Core** | Python package manager | uv |
| **Core** | JS package manager | pnpm |
| **Core** | Database | PostgreSQL |
| **Core** | Database setup | One instance, two schemas (api + analytics) |
| **Core** | Analytics architecture | Separate microservice |
| **Core** | URL format | Both (random by default, custom slugs optional) |
| **Observability** | Logging | structlog (JSON) |
| **Observability** | Metrics | Prometheus + Grafana |
| **Observability** | Tracing | OpenTelemetry |
| **Observability** | Error tracking | Sentry |
| **Security** | Rate limiting | slowapi |
| **Security** | Secrets | .env files (local), docker secrets (prod) |
| **DX** | Python linting | Ruff |
| **DX** | Python types | mypy |
| **DX** | JS linting | ESLint + Prettier |
| **DX** | Pre-commit | pre-commit framework |
| **DX** | Task runner | Makefile |
| **Infra** | Orchestration | Kubernetes |
| **Infra** | Local K8s | Docker Desktop |
| **Infra** | K8s packaging | Helm (optional) |
| **Infra** | Hosting | Decide later (GKE/EKS/AKS recommended for K8s) |
| **Frontend** | Analytics data access | Through API service (proxied) |
| **Frontend** | Charting library | Chart.js + react-chartjs-2 |
| **Frontend** | Auth token storage | httpOnly cookies |
| **API** | Versioning | /api/v1/ prefix |

---

## Database Schema (Draft)

### API Schema (`api`)

```sql
-- Users table
CREATE TABLE api.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    provider VARCHAR(50) NOT NULL,        -- 'github' or 'google'
    provider_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Links table
CREATE TABLE api.links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES api.users(id) ON DELETE CASCADE,
    short_code VARCHAR(20) UNIQUE NOT NULL,  -- e.g., 'abc123' or 'my-custom-slug'
    original_url TEXT NOT NULL,
    is_custom BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP                      -- optional expiration
);

CREATE INDEX idx_links_short_code ON api.links(short_code);
CREATE INDEX idx_links_user_id ON api.links(user_id);
```

### Analytics Schema (`analytics`)

```sql
-- Raw click events
CREATE TABLE analytics.clicks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    link_id UUID NOT NULL,                    -- references api.links(id)
    clicked_at TIMESTAMP DEFAULT NOW(),
    referrer TEXT,
    user_agent TEXT,
    ip_address INET,
    country VARCHAR(2),                       -- ISO country code
    city VARCHAR(255)
);

CREATE INDEX idx_clicks_link_id ON analytics.clicks(link_id);
CREATE INDEX idx_clicks_clicked_at ON analytics.clicks(clicked_at);

-- Aggregated stats (hourly)
CREATE TABLE analytics.link_stats_hourly (
    link_id UUID NOT NULL,
    hour TIMESTAMP NOT NULL,
    click_count INTEGER DEFAULT 0,
    unique_visitors INTEGER DEFAULT 0,
    PRIMARY KEY (link_id, hour)
);

-- Aggregated stats (daily)
CREATE TABLE analytics.link_stats_daily (
    link_id UUID NOT NULL,
    date DATE NOT NULL,
    click_count INTEGER DEFAULT 0,
    unique_visitors INTEGER DEFAULT 0,
    top_referrers JSONB,
    top_countries JSONB,
    PRIMARY KEY (link_id, date)
);
```

---

## Verification Plan

After each phase, we'll verify the implementation works:

### Phase 1 Verification

- [ ] `docker-compose up` starts PostgreSQL + Redis without errors
- [ ] `make dev-api` starts API service on localhost:8000
- [ ] `make dev-analytics` starts Analytics service on localhost:8001
- [ ] `make dev-client` starts React dev server on localhost:5173
- [ ] `make lint` runs without errors
- [ ] Pre-commit hooks trigger on `git commit`
- [ ] HTTPS works locally (https://localhost:5173)

### Phase 2 Verification

- [ ] `POST /api/v1/links` creates a short link (test with curl/httpie)
- [ ] `GET /api/v1/links` returns user's links
- [ ] `GET /{short_code}` redirects to original URL (note: redirect is NOT versioned)
- [ ] Redirect is cached in Redis (check with `redis-cli GET`)
- [ ] OAuth login with GitHub works end-to-end
- [ ] Rate limiting triggers after threshold
- [ ] Prometheus metrics visible at `/metrics`
- [ ] Logs output as JSON with request IDs

### Phase 3 Verification

- [ ] Click events appear in `analytics.clicks` table after redirect
- [ ] Country/city populated from IP lookup
- [ ] Aggregation job populates hourly/daily tables
- [ ] `GET /analytics/{link_id}/summary` returns correct totals
- [ ] Analytics service logs show events processed

### Phase 4 Verification

- [ ] Login page renders, OAuth buttons work
- [ ] After login, redirected to dashboard
- [ ] Dashboard shows list of user's links
- [ ] Create link form works, shows short URL
- [ ] Link detail page shows charts with analytics
- [ ] Logout works, protected routes redirect to login

### Phase 5 Verification

- [ ] GitHub Actions workflow passes on push
- [ ] Docker images build successfully
- [ ] `pytest` passes with >80% coverage
- [ ] Playwright tests pass in CI

### Phase 6 Verification

**Local Kubernetes:**

- [ ] `kubectl get nodes` shows Docker Desktop node ready
- [ ] `kubectl apply -f k8s/` deploys all resources
- [ ] `kubectl get pods -n brevi` shows all pods running
- [ ] All pods pass liveness and readiness probes
- [ ] Ingress routes traffic correctly to services
- [ ] App accessible via `localhost` through Ingress

**Scaling:**

- [ ] HPA scales API pods under load (use `hey` or `k6` for load testing)
- [ ] Pods respect resource limits

**Helm (if used):**

- [ ] `helm install brevi ./charts/brevi -f values-dev.yaml` works
- [ ] `helm upgrade` applies changes correctly

**Production:**

- [ ] `pulumi up` provisions K8s cluster without errors
- [ ] `kubectl` connects to production cluster
- [ ] Helm/manifests deploy successfully to prod
- [ ] Production domain resolves with valid TLS
- [ ] Grafana dashboards show live pod metrics
- [ ] Alerts fire on simulated errors

---

## Learning Topics Covered

This project will give you hands-on experience with:

| Category | Topics |
|----------|--------|
| **Python Backend** | FastAPI, async/await, SQLAlchemy 2.0, Pydantic, Alembic migrations |
| **Frontend** | React 18, JavaScript, TanStack Query, React Router, Tailwind, shadcn/ui |
| **Databases** | PostgreSQL schemas, indexing, JSONB, connection pooling |
| **Caching** | Redis caching patterns, cache invalidation, Pub/Sub messaging |
| **Auth** | OAuth 2.0 flow, JWT/sessions, protected routes |
| **Microservices** | Service separation, event-driven architecture, shared schemas |
| **Observability** | Structured logging, Prometheus metrics, OpenTelemetry tracing, Sentry |
| **Security** | CORS, rate limiting, input validation, security headers |
| **Testing** | pytest, Vitest, testcontainers, Playwright E2E |
| **DevOps** | Docker multi-stage builds, GitHub Actions, preview environments |
| **Kubernetes** | Pods, Deployments, Services, Ingress, ConfigMaps, Secrets, HPA, Helm |
| **Infrastructure** | Pulumi IaC, cloud K8s clusters (GKE/EKS/AKS), Grafana dashboards |
| **DX** | Ruff, mypy, pre-commit hooks, Makefile automation |

---

## Next Immediate Steps

When ready to start Phase 1:

1. Create the folder structure (`services/api/`, `services/analytics/`, `client/`, etc.)
2. Remove existing venv from root
3. Initialize API service with `uv init`
4. Initialize Analytics service with `uv init`
5. Initialize shared package
6. Initialize React client with `pnpm create vite`
7. Create docker-compose.yml for PostgreSQL + Redis
8. Set up Makefile with common commands
9. Configure pre-commit hooks
10. Verify everything runs with `docker-compose up` and `make dev-*`
