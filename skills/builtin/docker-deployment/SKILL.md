---
name: docker-deployment
description: Containerization, Dockerfile creation, docker-compose orchestration, and deployment setups.
target_agent: agent5
---

# Docker Deployment & Containerization Skill

When generating deployment configurations or Dockerfiles:

## Key Guidelines
1. **Dockerfile Best Practices**:
   - Use lightweight base images (e.g., `python:3.11-slim` or `node:20-alpine`).
   - Copy dependency manifests (`requirements.txt`, `package.json`) before copying source code to maximize build layer caching.
2. **Docker Compose**:
   - Define multi-container setups (web frontend, backend API, database) cleanly in `docker-compose.yml`.
   - Configure environment variables and health check probes.

