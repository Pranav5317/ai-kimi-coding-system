---
name: express-backend
description: NodeJS and Express REST API development, routing, middleware, controllers, and JSON responses
target_agent: agent2
---

# Express REST API Backend Development Skill

When building or modifying NodeJS / Express backend services:

1. **Routing & Modules**:
   - Organize routes using `express.Router()` in `routes/` or `controllers/`.
   - Use `express.json()` middleware for JSON body parsing.

2. **Middleware & Error Handling**:
   - Implement standard error-handling middleware `(err, req, res, next) => { ... }`.
   - Ensure CORS headers are enabled via `cors` middleware.

3. **Response Standard**:
   - Return structured JSON payloads `{ "status": "success", "data": ... }`.
   - Use appropriate HTTP status codes (200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found, 500 Internal Error).

