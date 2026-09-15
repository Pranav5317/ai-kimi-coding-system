---
name: prisma-orm
description: Prisma schema modeling (schema.prisma), database migrations, and type-safe Prisma Client queries.
target_agent: agent3
---

# Prisma ORM Database Skill

When designing database schemas or writing database queries with Prisma:

## Key Guidelines
1. **Schema Modeling (`schema.prisma`)**:
   - Define data models with explicit primary keys (`@id @default(autoincrement())` or `@default(uuid())`), relations (`@relation`), and indexes (`@@index`).
   - Use `@updatedAt` and `@default(now())` timestamps.

2. **Migrations & Queries**:
   - Use `npx prisma migrate dev` for database migrations.
   - Use type-safe `prisma.<model>.findMany()`, `create()`, `update()`, and `delete()` queries with select/include clauses.

