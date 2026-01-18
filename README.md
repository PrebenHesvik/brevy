# Brevy

A URL shortener with analytics, built for learning modern software engineering practices.

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis
- **Frontend**: React, JavaScript, Vite, Tailwind CSS, shadcn/ui
- **Infrastructure**: Docker, Kubernetes (planned)

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) - Python package manager
- [Node.js 20+](https://nodejs.org/)
- [pnpm](https://pnpm.io/installation) - Node package manager
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [pre-commit](https://pre-commit.com/#install) - Git hooks framework
- [mkcert](https://github.com/FiloSottile/mkcert#installation) - Local HTTPS certificates (optional)

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/PrebenHesvik/brevy.git
cd brevy

# Copy environment file
cp .env.example .env
```

### 2. Install Dependencies

```bash
# Install all dependencies (Python + Node + pre-commit hooks)
make install
```

Or install individually:

```bash
# Python services
cd services/api && uv sync --all-extras
cd services/analytics && uv sync --all-extras

# React client
cd client && pnpm install

# Pre-commit hooks
pre-commit install
```

### 3. Start Docker Services

```bash
# Start PostgreSQL and Redis
make docker-up

# Verify services are healthy
docker-compose ps
```

### 4. Start Development Servers

```bash
# Start all services (API + Analytics + Client)
make dev
```

Or start individually in separate terminals:

```bash
# Terminal 1: API service (http://localhost:8000)
make dev-api

# Terminal 2: Analytics service (http://localhost:8001)
make dev-analytics

# Terminal 3: React client (http://localhost:5173)
make dev-client
```

### 5. Verify Setup

- **API**: http://localhost:8000 (should show welcome message)
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Analytics**: http://localhost:8001 (should show welcome message)
- **Client**: http://localhost:5173 (React app)

## Local HTTPS (Optional)

For OAuth callbacks, you may need HTTPS locally:

```bash
# Install mkcert (one-time setup)
# Windows (with Chocolatey): choco install mkcert
# macOS: brew install mkcert
# Linux: see https://github.com/FiloSottile/mkcert#installation

# Generate certificates
make certs
```

This creates certificates in `./certs/` for localhost.

## Available Commands

Run `make help` to see all available commands:

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies |
| `make dev` | Start all services |
| `make dev-api` | Start API service only |
| `make dev-analytics` | Start Analytics service only |
| `make dev-client` | Start React client only |
| `make docker-up` | Start PostgreSQL + Redis |
| `make docker-down` | Stop containers |
| `make lint` | Run all linters |
| `make lint-fix` | Fix linting issues |
| `make format` | Format all code |
| `make test` | Run all tests |
| `make clean` | Remove build artifacts |

## Project Structure

```
brevy/
├── services/
│   ├── api/                 # Main API service (FastAPI)
│   │   ├── app/
│   │   │   ├── api/         # Route handlers
│   │   │   ├── core/        # Config, security
│   │   │   ├── models/      # SQLAlchemy models
│   │   │   ├── schemas/     # Pydantic schemas
│   │   │   └── services/    # Business logic
│   │   └── tests/
│   │
│   └── analytics/           # Analytics service (FastAPI)
│       ├── app/
│       │   ├── consumers/   # Redis Pub/Sub consumers
│       │   ├── models/      # Analytics models
│       │   └── aggregators/ # Data aggregation
│       └── tests/
│
├── packages/
│   └── shared/              # Shared Python schemas
│
├── client/                  # React frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── hooks/           # Custom hooks
│   │   └── api/             # API client
│   └── tests/
│
├── scripts/                 # Utility scripts
├── docker-compose.yml       # Local development containers
├── Makefile                 # Development commands
└── .pre-commit-config.yaml  # Git hooks
```

## Development

### Code Quality

Pre-commit hooks run automatically on `git commit`. To run manually:

```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
```

### Testing

```bash
# Run all tests
make test

# Run specific service tests
make test-api
make test-analytics
make test-client
```

### Database

The database is initialized with two schemas:
- `api` - Users and links
- `analytics` - Click data and aggregations

To reset the database:

```bash
make docker-clean
make docker-up
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - Session/JWT signing key
- `GITHUB_CLIENT_ID/SECRET` - GitHub OAuth credentials
- `GOOGLE_CLIENT_ID/SECRET` - Google OAuth credentials

## License

MIT
