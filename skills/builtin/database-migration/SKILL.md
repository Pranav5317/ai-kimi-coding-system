---
name: database-migration
description: Relational database schema management, SQL migrations, index optimizations, and ORM mapping.
target_agent: agent3
---

# Database Migration & Schema Skill

When modifying or creating database schemas, indices, or ORM models:

## Key Guidelines
1. **Schema Integrity**:
   - Ensure foreign key constraints, column indices, and default values are explicitly specified.
   - Use migrations for schema changes rather than mutating live tables directly.
2. **Data Consistency**:
   - Keep SQL queries parameterized to prevent SQL injection vulnerabilities.
3. **ORM Mapping**:
   - Align ORM model classes (e.g. SQLAlchemy, Prisma, Drizzle) precisely with table column definitions.

