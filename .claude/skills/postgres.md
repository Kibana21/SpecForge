# PostgreSQL Best Practices for CRAFT

Apply these rules whenever writing SQLAlchemy models, Alembic migrations, or database queries.

---

## Schema Design

- Use **UUID v4** as primary keys (`sqlalchemy.dialects.postgresql.UUID`), not auto-incrementing integers. Prevents ID enumeration attacks and simplifies distributed systems.
- Always add `created_at` (server default `now()`) and `updated_at` (auto-updated via SQLAlchemy event) columns to every table.
- Use PostgreSQL **enums** for columns with fixed value sets (roles, statuses, types). Define as `sqlalchemy.Enum` with `create_type=True`. Name the enum type explicitly (e.g., `user_role`, `artifact_type`).
- Use **JSON/JSONB** columns only for genuinely flexible data (briefs, content). For structured fields, use proper columns with types — they're queryable, indexable, and validated at the DB level.
- Add `NOT NULL` constraints on every column that should always have a value. Be explicit — don't rely on application-level validation alone.
- Add `UNIQUE` constraints where business logic requires uniqueness (e.g., `users.email`, composite unique on `project_members(project_id, user_id)`).
- Use **foreign keys** with `ON DELETE CASCADE` or `ON DELETE SET NULL` explicitly. Never leave FK delete behavior undefined.
- Soft deletes: use a `deleted_at` timestamp column (nullable). Filter out deleted rows in queries. This preserves audit trails.

## Indexes

- **Always index foreign keys.** PostgreSQL does NOT auto-create indexes on FK columns (unlike MySQL). Every `_id` column that is a foreign key needs an explicit index.
- Add indexes on columns used in `WHERE`, `ORDER BY`, or `JOIN` clauses that query large tables.
- Use **partial indexes** for queries on a subset of rows (e.g., `CREATE INDEX idx_active_rules ON compliance_rules (id) WHERE is_active = true`).
- Use **GIN indexes** on JSONB columns that are queried with `@>`, `?`, or `?&` operators.
- For the pgvector `embedding` column, use an **IVFFlat or HNSW index**: `CREATE INDEX ON compliance_documents USING hnsw (embedding vector_cosine_ops)`.
- Name indexes explicitly and consistently: `idx_{table}_{column}` or `idx_{table}_{column1}_{column2}`.
- Don't over-index. Every index slows down writes. Only index what you actually query.

## Queries (SQLAlchemy)

- Always use **async sessions** (`AsyncSession`) with `async with` context manager. Never leave sessions open.
- Use `select()` statement API (SQLAlchemy 2.0 style), not the legacy `session.query()` API.
- **Eager load relationships** when you know you'll need them — use `selectinload()` or `joinedload()` to avoid N+1 queries. Never lazy-load inside a loop.
- Use `session.scalars()` for single-column results, `session.execute()` for multi-column results.
- Always `.limit()` and `.offset()` paginated queries. Never fetch unbounded result sets.
- Use `func.count()` over `select(Table)` with `len()` for counting — let the database count, not Python.
- For bulk inserts, use `session.execute(insert(Model).values(list_of_dicts))` — not individual `session.add()` calls in a loop.
- Wrap multi-step operations in explicit transactions (`async with session.begin()`). Don't rely on auto-commit.

## Migrations (Alembic)

- **One migration per logical change.** Don't cram unrelated schema changes into one migration.
- Always write both `upgrade()` and `downgrade()` functions. Test downgrade works.
- **Never modify a migration that has been applied** to any environment. Create a new migration instead.
- For adding a `NOT NULL` column to an existing table: first add as nullable, backfill data, then alter to `NOT NULL` in a separate migration.
- Name migration files descriptively: `002_add_purpose_to_projects.py`, not `002_update.py`.
- Run `alembic check` to detect model/migration drift before committing.
- Always enable the pgvector extension in the first migration: `op.execute('CREATE EXTENSION IF NOT EXISTS vector')`.

## Connection Management

- Use **connection pooling** via SQLAlchemy's built-in pool. Settings:
  - `pool_size=10` (concurrent connections)
  - `max_overflow=20` (burst connections)
  - `pool_timeout=30` (seconds to wait for connection)
  - `pool_recycle=1800` (recycle connections every 30 min to avoid stale connections)
  - `pool_pre_ping=True` (test connections before use)
- Use `NullPool` for tests (fresh connection per test).
- Set `statement_timeout` on the database role (e.g., 30 seconds) to prevent runaway queries.

## Performance

- Use `EXPLAIN ANALYZE` on slow queries to understand the query plan. Look for sequential scans on large tables.
- For dashboard/analytics queries, consider **materialized views** refreshed on a schedule, or cache results in Redis with a TTL.
- Use `SELECT ... FOR UPDATE` only when you need row-level locking (e.g., updating remix_count). Use `SKIP LOCKED` for queue-like patterns.
- Batch large data operations (e.g., compliance document chunking) — don't load entire large documents into memory at once.

## Data Integrity

- Use **check constraints** for business rules that can be expressed as simple conditions (e.g., `CHECK (compliance_score >= 0 AND compliance_score <= 100)`).
- Use **database-level defaults** (`server_default`) for values that should always be set, even if the application layer fails (e.g., `created_at`, `status`).
- Validate data at both the application level (Pydantic) AND the database level (constraints). Defense in depth.
