---
name: fastapi-backend
description: Specialized guidelines for building FastAPI REST APIs with Pydantic, CORS, and clean modular routing.
target_agent: agent2
---

# FastAPI Backend Development Skill

When building or refactoring FastAPI backend services, adhere strictly to these architecture standards:

## Key Guidelines
1. **Modular Architecture**:
   - Keep routing definitions in `routes/` or `api/` modules.
   - Use Pydantic models for request bodies and response schemas.
2. **CORS & Middleware**:
   - Include `CORSMiddleware` with configurable origins when building APIs consumed by web frontends.
3. **Error Handling**:
   - Raise explicit `HTTPException(status_code=..., detail=...)` for validation or resource errors.
4. **Endpoint Design**:
   - Use standard RESTful conventions (`GET`, `POST`, `PUT`, `DELETE`).
   - Include type annotations on all path parameters and dependency injections.

