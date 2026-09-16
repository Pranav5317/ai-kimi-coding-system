---
name: docker-deployment
description: Containerization using Dockerfile, docker-compose.yml, multi-stage builds, and deployment setups
target_agent: agent5
---

# Docker Containerization & Deployment Skill

When containerizing or setting up deployment environments:

1. **Dockerfile Best Practices**:
   - Use official slim/alpine base images (e.g. `node:18-alpine`, `python:3.11-slim`).
   - Use multi-stage builds to separate build environments from runtime artifacts.
   - Set environment variables (`ENV`) and expose container ports (`EXPOSE`).

2. **Docker Compose Orchestration**:
   - Create `docker-compose.yml` defining services, volumes, networks, and environment variables.
   - Configure health checks (`healthcheck`) and restart policies (`restart: unless-stopped`).

