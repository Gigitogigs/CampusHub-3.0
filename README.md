# CampusHub 3.0

CampusHub 3.0 is a multi-tenant university platform built with **Django 6.1**, **Django REST Framework**, and **PostgreSQL 18**. Each university acts as an isolated tenant (`universities.University`), with strict authentication, tenant-scoping middleware, and role-based access control.

---

## Documentation

Start here to understand the architecture, data model, and core request lifecycle:

| Document | Description |
|---|---|
| **[Authentication, Middleware, and Permissions Guide](docs/auth-middleware-permissions.md)** | Onboarding guide for new developers: key technologies, request lifecycle, session invalidation (`auth_version`), `TenantMiddleware`, role-based permissions, and step-by-step user walkthroughs. |
| **[Diagram Pack and Django App Inventory](docs/Diagrams-and-Django-Apps.md)** | Full ERDs (D1–D6), table-to-isolation map, layered backend architecture, app dependency graph, and prohibited import boundaries. |

---

## Tech Stack

- **Backend:** Python 3.13, Django 6.1.3, Django REST Framework 3.18.3
- **Database:** PostgreSQL 18 (`psycopg` 3.3.9) — PostgreSQL is the **only** supported database backend
- **Security & Auth:** DRF `SessionAuthentication`, custom `AccountStatusBackend`, Argon2 password hashing (`argon2-cffi`), UUIDv7 primary keys (`uuid6`)
- **Config & CORS:** `dj-database-url`, `python-dotenv`, `django-cors-headers`

---

## Project Structure

### Implemented Apps

| App | Responsibility |
|---|---|
| `config/` | Django settings, root URL routing (`config/urls.py`), WSGI/ASGI entrypoints |
| `core/` | Tenant-scoping infrastructure (`TenantMiddleware`, `tenant_scope`, `TenantScopedManager`, `TenantOwnedModel`), platform-level `IsPlatformAdmin` permission |
| `universities/` | University registry (`University`, `EmailDomain`), public/admin serializers, views, and permissions |
| `accounts/` | Custom user model (`accounts.User`), `RoleAssignment`, `EmailToken`, `AccountStatusBackend`, tenant-scoped selectors, and account permissions |
| `category/` | Global reference category app (scaffolded) |
| `media/` | Media service app (scaffolded) |
| `audit/` | Audit logging app (scaffolded) |

> **Roadmap:** Product-domain apps shown in the architecture diagrams (`clubs`, `events`, `businesses`, `marketplace`, `cart`, `orders`, `moderation`, `notifications`) are planned for future implementation phases.

---

## Local Setup

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your local PostgreSQL credentials and secret key:

```env
DATABASE_URL=postgresql://campushub:change-this-password@127.0.0.1:5432/campushub
OPS_DATABASE_URL=
SECRET_KEY='your-dev-secret-key'
DJANGO_DEBUG=True
```

- `DATABASE_URL` **must** be a valid PostgreSQL connection string (`config/settings.py` fails fast if it is missing or non-PostgreSQL).
- `OPS_DATABASE_URL` is optional in development and configures the `ops` database alias used by platform-admin user selectors (`accounts/selectors.py`).

### 3. Apply migrations and run checks

```powershell
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
```

### 4. Run the development server

```powershell
python manage.py runserver
```

---

## Running Tests

All tests run against PostgreSQL (no SQLite fallback is configured):

```powershell
# Run the full test suite
python manage.py test

# Run tests for specific apps
python manage.py test accounts universities core
```

---

## API Routes Overview

Defined in `config/urls.py`:

- `admin/` — Django admin site (`accounts.User`)
- `api/v1/universities/` — Canonical university registry routes (`universities/urls.py`)
  - `GET /api/v1/universities/` — List universities (platform admin)
  - `POST /api/v1/universities/create/` — Create/onboard university (platform admin)
  - `GET /api/v1/universities/public/<slug>/` — Public active university profile (`AllowAny`)
  - `PATCH /api/v1/universities/<uuid:pk>/` — Update university (platform admin or scoped university admin)
  - `POST /api/v1/universities/<uuid:pk>/archive/` — Soft-archive university (platform admin)
- `api/accounts/` — Account routes and legacy university list compatibility alias (`accounts/urls.py`)
