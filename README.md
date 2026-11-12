# Warehouse Management API

A small warehouse management backend built with **FastAPI**, **SQLAlchemy** (ORM) and **SQLite**, designed around
what I saw every day in 10 years of warehouse work.

> **Status: work in progress.** Version 1 (items, loading, picking) and version 2
> (operators, stock movement history, authentication and roles) are complete.
> Next steps are in the [roadmap](#roadmap).

## What it does

- **Items catalogue**: create, list (with filters by category and max price), read, update and delete items
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
  **foreign keys** (`PRAGMA foreign_keys = ON` on every connection). An operator or item
  that doesn't exist cannot be used, and a movement can never point to nothing.
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
- **Checks always run in the same order**: who you are (`401`) → what you can do (`403`) →
  the data (`404` / `400` / `409`). An operator can't use a `404` vs `403` difference
  to find out which users exist.
- **Login doesn't reveal which usernames exist**: wrong username and wrong password give
  the same `401` with the same message.
- **Users are created only by a manager**, so nobody can register themselves as `responsabile`.
  The first manager is created at startup, with the password read from an environment variable
  (a `.env` file kept outside the project).
- **No SQL built by hand**: every query goes through the SQLAlchemy ORM (`select(...).where(...)`),
  which sends the values as bound parameters, never as text pasted into the SQL, against SQL injection.

### Code organization

The project is split into modules, one per responsibility:

```
app/
├── gestionale.py          # creates the FastAPI app, mounts the routers, login endpoint
├── database.py            # engine, ORM models (one class per table), session dependency, helpers
├── schemas.py             # Pydantic models: what the API accepts as input
├── security.py            # password hashing, token check (401) and role checks (403)
├── seed.py                # creates the first manager at startup
├── routers/
│   ├── catalogo.py        # items, loading, picking, item history
│   ├── utenti.py          # users
│   └── movimenti.py       # movement history
└── test_gestionale_orm.py # tests
```

- **Each group of endpoints is an `APIRouter`** with its own prefix and tag, mounted in
  `gestionale.py` with `include_router`.
- **Dependencies between modules go in one direction only**: `database.py` is the lowest layer
  and imports nothing from the project; `security.py`, `seed.py` and the routers import from it.
  This avoids circular imports. Every import uses the `app.` prefix, so each module is loaded once.
- **One database session per request**, opened by a `yield` dependency and closed automatically
  at the end of the request. FastAPI caches dependencies within a request, so the route and all
  its checks (token, role, item lookup) share the same session and are saved by a single `commit`.
- **Endpoints never return ORM objects directly**: they are unpacked into plain dictionaries,
  so internal fields like the password hash can never end up in a response.

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
| `GET` | `/catalogo` | operator, manager | List items, optional filters `categoria` and `prezzo_inferiore_a` |
| `GET` | `/catalogo/{id_prodotto}` | operator, manager | Read one item |
| `PATCH` | `/catalogo/{id_prodotto}` | manager | Update name, price or category |
| `DELETE` | `/catalogo/{id_prodotto}` | manager | Delete an item (`409` if it has movements other than `nuovo articolo`) |
| `PATCH` | `/catalogo/{id_prodotto}/carico` | operator, manager | Load stock (records a movement) |
| `PATCH` | `/catalogo/{id_prodotto}/prelievo` | operator, manager | Pick stock (records a movement, reports missing pieces) |
| `GET` | `/movimenti` | manager | Full movement history with operator and item names (through ORM relationships), optional filter `data` (YYYY-MM-DD) |
| `GET` | `/movimenti/{id_utente}` | manager | Movements of one operator, optional filters `tipo_movimenti` (`carico` / `prelievo` / `nuovo articolo`) and `data` |
| `GET` | `/catalogo/{id_prodotto}/movimenti` | manager | Movements of one item, optional filter `data` (`404` if the item doesn't exist) |

## Database

Four tables in SQLite, defined as SQLAlchemy models and created automatically at startup:

- `articoli`: id, name, price, category, quantity, insertion date, last movement date
- `utenti`: id, name, username (unique, lowercase), role, password hash
- `movimenti`: id, operator id, item id, quantity, type (`nuovo articolo` / `carico` / `prelievo`), date, stock after movement
- `sessioni`: token, user id, expiry (deleted together with their user, via cascade)

## Run it locally

```bash
pip install "fastapi[standard]" sqlalchemy "pwdlib[argon2]" python-dotenv
```

Create a file `~/Secret/.env` (outside the project, never committed) with the password
of the first manager:

```
PASSWORD_RESPONSABILE=your_password
```

Then start the server from the project folder (the one that contains `app/`):

```bash
uvicorn app.gestionale:app --reload
```

Open http://127.0.0.1:8000/docs, call `POST /login` with the first manager's username
(set in `app/seed.py`) and password, copy the token, click **Authorize** and paste it:
from then on every endpoint can be tried from the browser.
The database file is created automatically on the first run.

## Tests

From the project folder:

```bash
pip install pytest
pytest
```

The tests run on a separate database: `app.dependency_overrides` replaces the session
dependency with one connected to a test database, which a pytest fixture drops, recreates
and fills with known data before every test, so each test starts from the same state and
never touches the real one. Foreign keys are enabled on the test database too, and a
dedicated test checks that the database really rejects a movement pointing to a missing
item (`IntegrityError` on commit). They cover the
normal cases and the edge ones: missing, invalid and expired tokens, wrong role,
validation errors, missing resources, deletion of items and users with movements.

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
- [ ] `requirements.txt`
- [x] Record the initial stock of a new item as a movement
- [x] Movement history of a single item
- [x] Test that foreign keys are really enforced by the database
- [x] Refactoring into modules (routers, security, schemas, seed)
- [ ] PostgreSQL and Docker

## Tech stack

Python · FastAPI · Pydantic · SQLAlchemy · SQLite · pwdlib (Argon2) · python-dotenv · pytest
