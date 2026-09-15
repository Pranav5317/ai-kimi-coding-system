---
name: django-backend
description: Django REST Framework (DRF), ModelSerializers, API ViewSets, routers, and Django ORM models.
target_agent: agent2
---

# Django REST Framework Backend Skill

When building Django or Django REST Framework (DRF) backend applications:

## Key Guidelines
1. **App Architecture**:
   - Structure functionality into modular Django apps (`apps/users`, `apps/orders`).
   - Define database models using `django.db.models.Model`.

2. **Django REST Framework**:
   - Use `ModelSerializer` for request/response serialization.
   - Use `ModelViewSet` or API views with `DefaultRouter` for RESTful CRUD endpoints.

3. **Authentication & Permissions**:
   - Configure DRF authentication classes (`JWTAuthentication` or `SessionAuthentication`) and permission classes (`IsAuthenticated`).

