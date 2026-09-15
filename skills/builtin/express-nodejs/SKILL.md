---
name: express-nodejs
description: Node.js Express REST API routes, custom middleware, async error handling, and JSON responses.
target_agent: agent2
---

# Express Node.js Backend Framework Skill

When building Node.js Express backend services or API endpoints:

## Key Guidelines
1. **Modular Router Architecture**:
   - Divide API routes using `express.Router()` (e.g., `routes/auth.js`, `routes/users.js`).
   - Separate route handlers from business logic and database queries.

2. **Middleware & Validation**:
   - Use `express.json()` and `cors()` middleware.
   - Validate request body payloads using `express-validator` or `zod`.

3. **Error Handling**:
   - Wrap async route handlers to catch errors and pass to centralized `next(err)` error middleware.

