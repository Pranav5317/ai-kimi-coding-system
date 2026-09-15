---
name: nestjs-backend
description: NestJS TypeScript modules, controllers, service providers, DTO validation pipes, and Dependency Injection.
target_agent: agent2
---

# NestJS Backend Framework Skill

When building NestJS TypeScript backend applications:

## Key Guidelines
1. **Modular Architecture**:
   - Group features into NestJS Modules (`@Module`), Controllers (`@Controller`), and Services (`@Injectable`).
   - Use Dependency Injection (`constructor(private readonly userService: UserService)`).

2. **DTO & Validation**:
   - Define Data Transfer Objects (DTOs) with `class-validator` decorators (`@IsString()`, `@IsEmail()`, `@IsNotEmpty()`).
   - Use global `ValidationPipe` for request payload validation.

3. **REST Endpoints**:
   - Decorate methods with `@Get()`, `@Post()`, `@Put()`, `@Delete()`, `@Body()`, and `@Param()`.

