# CLAUDE.md

Guidance for AI coding sessions in this repo. README.md is the source of truth for the
project's current state. Read it first.

BiletFlow is self-service event ticketing for Kazakhstan (CSCI 361 university project).
"SRS x.y" references point to the Software Requirements Specification, which is in the
repo: `docs/srs/BiletFlow_SRS_v0.3.pdf` is the authoritative copy, and `docs/srs/srs.md` is
a searchable text extract of it. Check requirements against the SRS itself. Cite the
section (e.g. "SRS 4.8") in code, tests and docs. If the SRS, a model docstring and the task
prompt disagree, say so rather than picking one silently. The scanner app's compliance
with the SRS is tracked in `docs/scanner-requirements-check.md`.

## Stack (do not change)

- **API** (`apps/api`): FastAPI, Pydantic v2, SQLAlchemy 2.0 async + asyncpg, Alembic,
  PostgreSQL 16, uv, ruff, mypy (strict), pytest
- **Web** (`apps/web`): Next.js (App Router, TypeScript, Tailwind)
- **Scanner** (`apps/scanner`): Expo (React Native, TypeScript)
- **Shared types** (`packages/api-types`): generated from the FastAPI OpenAPI schema with
  openapi-typescript. Regenerate them, never edit them by hand.
- JS workspaces use **npm** (pnpm is not used).

Do not add, swap, or remove frameworks or major libraries without asking first.

## Data model conventions

- UUID primary keys via `uuid_pk()` in `app/models/base.py`.
- Money is `BigInteger` whole KZT (`money_kzt()`, `*_kzt` columns). No floats or decimals.
- Every timestamp is TIMESTAMPTZ. `Base.type_annotation_map` handles `Mapped[datetime]`.
- Enums live in `app/enums.py` as `StrEnum`s with **lowercase values**. Build columns only
  with `pg_enum()`, because partial-index predicates compare against the lowercase values.
- Reuse the existing models and enums. If a model change is truly needed, explain why
  first. Then add a **new** Alembic migration (never edit `0001_initial_schema.py`) and
  make sure `uv run alembic check` passes.
- Event display time zones are IANA names (e.g. `Asia/Almaty`), validated with `zoneinfo`.

## Code rules

- **Async only.** Never open a sync session or engine. `DATABASE_URL` must be
  `postgresql+asyncpg://...`.
- **Never trust the client** for roles, ownership, or IDs the server can determine
  (current user, organizer profile, event owner, status, slug). Derive them server-side.
- Self-registration may choose only `attendee` or `organizer`. `platform_admin` is never
  self-assignable, and event admins come from `StaffAssignment`.
- Keep routers thin. Put business logic in `app/services/`, request/response models in
  `app/schemas/`, and auth/permission dependencies in `app/deps.py`.
- Use one error response shape everywhere:
  `{"error": {"code", "message", "details"}}`.
- Auth, login, and forgot-password responses must not reveal whether an email is
  registered.
- A resource the caller may not see returns 404, not 403.
- Put all user-facing web strings in one module (translations come later).

## Web design system

- Build every web screen from the design system: tokens in `apps/web/src/app/globals.css`
  (one `@theme` block) and shared components in `apps/web/src/components/ui.tsx`,
  `event-card.tsx` (Poster, EventCard), `ticket-card.tsx`, `confirm-dialog.tsx`,
  `site-header.tsx` and `site-footer.tsx`. Don't add raw Tailwind palette colours
  (`gray-*`, `red-*`, ...) or hex values; add a token instead. The rationale and the WCAG
  contrast table are in `docs/design-direction.md`.
- Keep the DEMO marker (`DemoBadge`, `Alert kind="demo"`) on every payment screen, keep
  visible focus styles, and check each new screen at 390px in kk and ru.
- Add every new route to `docs/redesign-checklist.md` and `apps/web/e2e/smoke.spec.ts`.

## Commands

Run from `apps/api`:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .      # `uv run ruff format .` to fix
uv run mypy .
uv run pytest                     # uses the separate *_test database, never the dev DB
uv run alembic upgrade head
uv run alembic check              # models and migrations must match
uv run alembic revision --autogenerate -m "..."   # then review the generated file
```

Run from the repo root:

```bash
cp .env.example .env              # never commit .env
docker compose up                 # db :5433, api :8000, mailpit :8025 (UI) / :1025 (SMTP)
```

All four API checks (ruff check, ruff format --check, mypy, pytest) must pass before a
phase or PR is considered done.

## Git

- Use one feature branch per phase or task, with small commits and clear imperative
  messages.
- Never commit to or push to `main`, never force-push, and never commit `.env` or secrets.
- Do not add `Co-Authored-By: Claude`, `Claude-Session:`, or "Generated with Claude Code"
  lines to commits or PR descriptions.
