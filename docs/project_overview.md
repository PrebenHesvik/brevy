# Brevi - URL Shortener with Analytics

## Project Purpose

A learning project focused on modern software engineering practices rather than complex business logic.

## Learning Objectives

| # | Topic | Application |
|---|-------|-------------|
| 1 | Modern architecture | API + separate analytics service, event-driven click tracking |
| 2 | Infrastructure as Code | Terraform/Pulumi for API, database, Redis, CDN |
| 3 | Claude Code workflow | Branch creation, feature development, PR workflow |
| 4 | Testing | Unit tests, integration tests, Playwright E2E |
| 5 | GitHub Actions | Lint, test, deploy, preview environments per PR |
| 6 | Monitoring | Redirect latency, error rates, popular links |
| 7 | Error handling | Invalid URLs, expired links, rate limiting |
| 8 | OAuth login | GitHub/Google authentication |
| 9 | Caching | Redis for high-volume redirect lookups |

## Core Features (v1)

- Create short links (authenticated)
- Redirect short URLs to destinations
- Track click analytics (count, referrer, location)
- Dashboard to view your links and stats

## Future Extensions

- QR code generation
- Custom domains
- Link expiration
- Team workspaces
- API keys for programmatic access
- Bulk link creation

## Why This Project?

- **Simple mental model** - Everyone understands URL shortening
- **Immediate usability** - Use it yourself from day one
- **Natural caching story** - Read-heavy workload perfect for Redis
- **Clear scaling path** - Easy to reason about as traffic grows
- **Small initial scope** - v1 achievable quickly, then iterate
