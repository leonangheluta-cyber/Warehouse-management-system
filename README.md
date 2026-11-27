# Warehouse Management API

A small warehouse management backend built with **FastAPI**, **Pydantic**, **SQLAlchemy** (ORM) and **PostgreSQL**
(schema managed with **Alembic** migrations), designed around what I saw every day in 10 years of warehouse work.

> **Status: work in progress.** Version 1 (items, loading, picking) and version 2
> (operators, stock movement history, authentication and roles) are complete.
> The project started on SQLite and has been moved to PostgreSQL with Alembic migrations.
> Next steps are in the [roadmap](#roadmap).

## What it does

- **Items catalogue**: create, list (with filters by name, category, max price, max quantity and insertion date), read, update and delete items
- **Loading and picking**: add or remove stock from an item
- **Users with roles**: *operators* (`addetto`) move the goods, *managers* (`responsabile`) control everything
- **Login with session tokens**: every request except login must carry a valid token
- **Movement history**: every loading and picking is recorded with *who*, *what*, *how many*, *when*
  and the *stock left after the movement*
- **Manager view**: a single endpoint that returns the full history with operator and item names
- **Operator report**: all movements of one operator, filterable by type and day
- **Item history**: all movements of one item, filterable by day

## Design choices

These are the decisions I'm most interested in, because they come from real warehouse situations.

### Warehouse logic

- **The history records what was actually picked, not what was requested.**
  If an operator asks for 10 pieces but only 3 are on the shelf, the movement records 3
  and the response reports the 7 missing pieces.
- **Each movement stores a snapshot of the stock after it.**
  The current stock in the items table only tells you how many pieces there are *now*;
  to know how many there were after a movement last Tuesday, the value has to be saved
  at the moment it happens.
- **Movements store codes, not names**, and are linked to items and operators with
  **foreign keys**, always enforced by PostgreSQL. An operator or item that doesn't exist
  cannot be used, and a movement can never point to nothing.
- **History is never deleted.** An item or a user that already has movements cannot be
  deleted: the API answers `409 Conflict` with a clear message.
  The only exception is an item that was never moved: its only movement is the automatic
  `nuovo articolo` record, so it can be deleted together with that record (e.g. an item
  inserted by mistake). The check and the deletions happen in the same transaction: if a
  real movement is found, the `409` stops the request and nothing is deleted.
- **The initial stock is part of the history.** Creating an item also records a
  `nuovo articolo` movement with the starting quantity, in the same commit.
- **All-or-nothing writes.** Stock update and movement record are committed together,
  once, at the end of the request: if one of the two fails, nothing is saved.

### Security

- **Passwords are never stored**: only their **Argon2** hash (with a random salt), via `pwdlib`.
- **Session tokens stored in a table, not JWT.** At login a random token (`secrets`) is saved
  in the `sessioni` table with an 8-hour expiry (one work shift). A token in a table can be
  revoked immediately by deleting its row.
- **Authentication and roles are FastAPI dependencies.** Each protected endpoint declares
  in its signature who can call it, through a chain of dependencies:
  `HTTPBearer` (reads the `Authorization: Bearer` header) → token check (`401`) → role check (`403`).
  A check cannot be forgotten inside the function body, and `/docs` shows the **Authorize** button.
  The role checks are declared once as `Annotated` aliases (`AddettoDep`, `ResponsabileDep`),
  so a route just asks for `id_utente: AddettoDep`.
- **Checks always run in the same order**: who you are (`401`) → what you can do (`403`) →
  the data (`404` / `400` / `409`). An operator can't use a `404` vs `403` difference
  to find out which users exist.
- **Login doesn't reveal which usernames exist**: wrong username and wrong password give
  the same `401` with the same message.
- **Users are created only by a manager**, so nobody can register themselves as `responsabile`.
  The first manager is created at startup, with the password read from an environment variable
  (a `.env` file kept outside the project).
- **The app connects to the database with a least-privilege user.** Not the PostgreSQL superuser:
  a dedicated role that can only read and write rows (`SELECT`, `INSERT`, `UPDATE`, `DELETE` on the
  tables, `USAGE` on the id sequences). It cannot create, alter or drop tables, and it has no access
  to `alembic_version`, the migrations registry. Migrations run with a different user, the owner of
  the tables. If the app's credentials leaked, the damage would stay limited to the rows.
- **No SQL built by hand**: every query goes through the SQLAlchemy ORM (`select(...).where(...)`),
  which sends the values as bound parameters, never as text pasted into the SQL, against SQL injection.

### Code organization

The project is split into modules, one per responsibility:

```
app/
├── gestionale.py          # creates the FastAPI app, its lifespan (startup code) and mounts the routers
├── database.py            # engine, ORM models (one class per table), SessionDep
├── dependencies.py        # "find or 404" dependencies for items and users (ArticoloDep, UtenteDep)
├── schemas.py             # Pydantic models: what the API accepts (input) and returns (response_model)
├── security.py            # password hashing, token check (401) and role checks (403: AddettoDep, ResponsabileDep)
├── seed.py                # creates the first manager (called once at startup)
├── routers/
│   ├── login.py           # login, returns a session token
│   ├── catalogo.py        # items, loading, picking, item history
│   ├── utenti.py          # users
│   └── movimenti.py       # movement history
└── test_gestionale_orm.py # tests
alembic/
└── versions/              # database migrations (the first one creates all the tables)
```

- **Each group of endpoints is an `APIRouter`** with its own prefix and tag, mounted in
  `gestionale.py` with `include_router`.
- **Dependencies between modules go in one direction only**: `database.py` is the lowest layer
  and imports nothing from the project; `security.py`, `seed.py` and the routers import from it.
  This avoids circular imports. Every import uses the `app.` prefix, so each module is loaded once.
- **The schema is managed by Alembic, not by the app.** Tables are created and changed only through
  migration files in `alembic/versions/` (applied with `alembic upgrade head`); the app no longer calls
  `create_all`, so there is a single source of truth for the database structure.
- **Startup code runs at startup, not at import.** The seed of the first manager
  runs in the app's `lifespan` (before its `yield`), once, when the server starts. Importing a module
  (as the tests do) no longer touches the database: the test `TestClient` doesn't run the lifespan, so
  the tests never write to the real database. The seed is idempotent: it creates the manager only if
  it doesn't exist yet, and hashes the password only in that case.
- **One database session per request**, opened by a `yield` dependency and closed automatically
  at the end of the request. The dependency is declared once in `database.py` as
  `SessionDep = Annotated[Session, Depends(apri_db)]`, so every route and check just asks for
  `session: SessionDep`. FastAPI caches dependencies within a request, so the route and all
  its checks (token, role, item lookup) share the same session and are saved by a single `commit`.
- **"Find or 404" lookups are reusable dependencies.** `ArticoloDep` and `UtenteDep`
  (`Annotated[..., Depends(...)]`) read the id from the path, load the row and answer `404`
  if it doesn't exist, before the route body runs. Routes just ask for `articolo: ArticoloDep`.
- **List filters are a Pydantic model.** The five optional filters of `GET /catalogo` are declared in
  one model (`FiltriCatalogo`) read from the query string with `Annotated[FiltriCatalogo, Query()]`:
  each filter adds a `.where()` to the same query, and invalid values (e.g. a negative quantity)
  are rejected with `422` by Pydantic before the route runs.
- **Input models are unpacked, not copied field by field.** A new item is built with
  `ArticoloORM(**data.model_dump(), ...)` (the category is lowercased first, the dates are added
  separately). The item `PATCH` uses `model_dump(exclude_unset=True)`, so only the fields the client
  actually sent are written with `setattr`; a field sent as `null` is skipped instead of erasing the
  stored value, and the category is always saved in lowercase.
- **Every endpoint declares its response shape with `response_model`.** Routes return the ORM
  objects and FastAPI filters them through Pydantic `...Out` models (`schemas.py`), keeping
  only the declared fields: internal fields like the password hash can never end up in a
  response, and every response shape is documented in `/docs`. Responses with more than one
  part use nested models (e.g. item + movement), and the full movement history follows the
  ORM relationships to include the operator and the item.

## Endpoints

All endpoints except `/login` require the header `Authorization: Bearer <token>`.

| Method | Path | Who | Description |
|---|---|---|---|
| `POST` | `/login` | everyone | Returns a session token (`401` on wrong credentials) |
| `POST` | `/utenti` | manager | Add a user with role `addetto` or `responsabile` (`409` if the username is taken) |
| `GET` | `/utenti` | manager | List all users |
| `GET` | `/utenti/{id_utente}` | manager | Read one user |
| `DELETE` | `/utenti/{id_utente}` | manager | Delete a user (`409` if they have movements) |
| `POST` | `/catalogo` | operator, manager | Add a new item and record its initial stock as a `nuovo articolo` movement |
| `GET` | `/catalogo` | operator, manager | List items, optional filters `nome` (partial, case-insensitive), `categoria`, `prezzo_massimo`, `quantita_massima` (both inclusive, `quantita_massima` must be ≥ 0) and `data_inserimento` (YYYY-MM-DD or a prefix like YYYY-MM) |
| `GET` | `/catalogo/{id_prodotto}` | operator, manager | Read one item |
| `PATCH` | `/catalogo/{id_prodotto}` | manager | Update name, price or category: only the fields sent are changed, `null` values are ignored |
| `DELETE` | `/catalogo/{id_prodotto}` | manager | Delete an item (`409` if it has movements other than `nuovo articolo`) |
| `PATCH` | `/catalogo/{id_prodotto}/carico` | operator, manager | Load stock (records a movement) |
| `PATCH` | `/catalogo/{id_prodotto}/prelievo` | operator, manager | Pick stock (records a movement, reports missing pieces) |
| `GET` | `/movimenti` | manager | Full movement history with operator and item names (through ORM relationships), optional filter `data` (YYYY-MM-DD) |
| `GET` | `/movimenti/{id_utente}` | manager | Movements of one operator, optional filters `tipo_movimenti` (`carico` / `prelievo` / `nuovo articolo`) and `data` |
| `GET` | `/catalogo/{id_prodotto}/movimenti` | manager | Movements of one item, optional filter `data` (`404` if the item doesn't exist) |

## Response shapes

All ids are returned as `id`. The main shapes:

- **User** (`UtenteOut`): `id`, `nome`, `username`, `ruolo` (never the password hash)
- **Item** (`ArticoloOut`): `id`, `nome`, `categoria`, `prezzo`, `quantita`, `data_inserimento`, `data_ultimo_movimento`
- **Movement** (`MovimentoOut`): `id`, `id_utente`, `id_articolo`, `quantita`, `tipo`, `data`, `giacenza_dopo_movimento`
- **New item / loading** (`ArticoloConMovimento`): `{"articolo": {...}, "movimento": {...}}`
- **Picking** (`ArticoloPrelevatoOut`): same as above plus `da_prelevare`, the pieces that were requested but missing
- **Full history** (`GET /movimenti`, `MovimentoCompletoOut`): each movement with
  `"utente": {"id", "nome"}` and `"articolo": {"nome"}` nested inside

## Database

Four tables in **PostgreSQL**, defined as SQLAlchemy models and created by the first **Alembic** migration:

- `articoli`: id, name, price, category, quantity, insertion date, last movement date
- `utenti`: id, name, username (unique, lowercase), role, password hash
- `movimenti`: id, operator id, item id, quantity, type (`nuovo articolo` / `carico` / `prelievo`), date, stock after movement
- `sessioni`: token, user id, expiry (deleted together with their user, via cascade)

Two database users, two connection strings:

- the **owner** of the tables (used only by Alembic to run migrations)
- the **app user**, with row-level permissions only (used by the running API)

## Run it locally

You need **PostgreSQL** installed and running (with pgAdmin or `psql`).

**1. Install the dependencies**, from the project folder (the one that contains `app/`):

```bash
pip install -r requirements.txt
```

**2. Create the database and the app user.** As the PostgreSQL superuser, create an empty database
(e.g. `gestionale_magazzino`) and a login role for the app (any name, e.g. `app_gestionale`):

```sql
CREATE ROLE app_gestionale WITH LOGIN PASSWORD 'choose_a_password';
```

**3. Create the `.env` file** in `~/Secret/.env` (outside the project, never committed) with three variables:

```
PASSWORD_RESPONSABILE=password_of_the_first_manager
POSTGRE_GESTIONALE=postgresql+psycopg://owner_user:owner_password@localhost:5432/gestionale_magazzino
POSTGRE_GESTIONALE_ADDETTO=postgresql+psycopg://app_gestionale:app_password@localhost:5432/gestionale_magazzino
```

`POSTGRE_GESTIONALE` is read by Alembic (`alembic/env.py`) to create the tables;
`POSTGRE_GESTIONALE_ADDETTO` is read by the app (`app/database.py`).

**4. Create the tables** with the migrations:

```bash
alembic upgrade head
```

**5. Give the app user its permissions**, after the tables exist (`ON ALL TABLES` only covers
the tables that exist at that moment), connected to `gestionale_magazzino` as the owner:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_gestionale;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_gestionale;
REVOKE ALL ON alembic_version FROM app_gestionale;
```

The sequence grant is needed because every `INSERT` takes the new id from the table's sequence,
which is a separate object with its own permissions.

**6. Start the server**:

```bash
fastapi dev app/gestionale.py
```

Open http://127.0.0.1:8000/docs, call `POST /login` with the first manager's username
(set in `app/seed.py`) and password, copy the token, click **Authorize** and paste it:
from then on every endpoint can be tried from the browser.

## Tests

From the project folder:

```bash
pytest
```

The tests run on a separate **SQLite** database file (no PostgreSQL needed to run them): `app.dependency_overrides` replaces the session
dependency with one connected to a test database, which a pytest fixture drops, recreates
and fills with known data before every test, so each test starts from the same state and
never touches the real one. Foreign keys are enabled on the test database too (with `PRAGMA foreign_keys = ON`, since SQLite has them off by default), and a
dedicated test checks that the database really rejects a movement pointing to a missing
item (`IntegrityError` on commit). They cover the
normal cases and the edge ones: missing, invalid and expired tokens, wrong role,
validation errors, missing resources, deletion of items and users with movements, and the
list filters (each filter test is checked to fail when the filter is removed).

## Roadmap

- [x] Movement history with filters (by operator, type, date)
- [x] Block the deletion of items and users that have movements (`409`)
- [x] Automated tests (pytest)
- [x] Login with session tokens and hashed passwords
- [x] Roles (operator / manager)
- [x] Authentication as FastAPI dependencies (`Depends` + `HTTPBearer`)
- [x] Operator role check as a dependency too
- [x] Database session as a `yield` dependency (one session per request, closed automatically)
- [x] Migration to SQLAlchemy ORM (endpoints and tests)
- [x] `requirements.txt`
- [x] Record the initial stock of a new item as a movement
- [x] Movement history of a single item
- [x] Test that foreign keys are really enforced by the database
- [x] Refactoring into modules (routers, security, schemas, seed, dependencies) with a shared `SessionDep`
- [x] Name and insertion-date filters on the item list
- [x] `response_model` on every endpoint (Pydantic output models instead of hand-built dictionaries)
- [x] `Annotated` dependency aliases for item/user lookups and role checks
- [x] Startup code with `lifespan` (table creation and seed of the first manager)
- [x] Pydantic model for the list filters, `quantita_massima` filter
- [x] PostgreSQL with Alembic migrations and a least-privilege database user
- [ ] Tests on PostgreSQL too
- [ ] Docker (API + PostgreSQL with docker compose)

## Tech stack

Python · FastAPI · Pydantic · SQLAlchemy · PostgreSQL (psycopg) · Alembic · pwdlib (Argon2) · python-dotenv · pytest · SQLite (tests)
