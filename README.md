# Warehouse Management API

A small warehouse management backend built with **FastAPI** and **SQLite**, designed around
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
- **Operator report**: all movements of one operator, filterable by type and day, with the total pieces loaded and picked

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
- **Every query uses `?` placeholders** (parameterized queries), never f-strings, against SQL injection.

### Code organization

- `database.py` holds the connection, the tables, the authentication dependencies and the
  helper functions (checks, row unpacking, movement creation); `gestionale.py` holds only the endpoints.

## Endpoints

All endpoints except `/login` require the header `Authorization: Bearer <token>`.

| Method | Path | Who | Description |
|---|---|---|---|
| `POST` | `/login` | everyone | Returns a session token (`401` on wrong credentials) |
| `POST` | `/utenti` | manager | Add a user with role `addetto` or `responsabile` (`409` if the username is taken) |
| `GET` | `/utenti` | manager | List all users |
| `GET` | `/utenti/{id_utente}` | manager | Read one user |
| `DELETE` | `/utenti/{id_utente}` | manager | Delete a user (`409` if they have movements) |
| `POST` | `/catalogo` | operator, manager | Add a new item |
| `GET` | `/catalogo` | operator, manager | List items, optional filters `categoria` and `prezzo_inferiore_a` |
| `GET` | `/catalogo/{id_prodotto}` | operator, manager | Read one item |
| `PATCH` | `/catalogo/{id_prodotto}` | manager | Update name, price or category |
| `DELETE` | `/catalogo/{id_prodotto}` | manager | Delete an item (`409` if it has movements) |
| `PATCH` | `/catalogo/{id_prodotto}/carico` | operator, manager | Load stock (records a movement) |
| `PATCH` | `/catalogo/{id_prodotto}/prelievo` | operator, manager | Pick stock (records a movement, reports missing pieces) |
| `GET` | `/movimenti` | manager | Full movement history with operator and item names (SQL `JOIN`), optional filter `data` (YYYY-MM-DD) |
| `GET` | `/movimenti/{id_utente}` | manager | Movements of one operator, optional filters `tipo_movimenti` (`carico` / `prelievo`) and `data`, with loaded and picked totals |

## Database

Four tables in SQLite:

- `articoli`: id, name, price, category, quantity, insertion date, last movement date
- `utenti`: id, name, username (unique, lowercase), role, password hash
- `movimenti`: id, operator id, item id, quantity, type (`carico` / `prelievo`), date, stock after movement
- `sessioni`: token, user id, expiry

## Run it locally

```bash
pip install "fastapi[standard]" "pwdlib[argon2]" python-dotenv
```

Create a file `~/Secret/.env` (outside the project, never committed) with the password
of the first manager:

```
PASSWORD_RESPONSABILE=your_password
```

Then start the server:

```bash
fastapi dev gestionale.py
```

Open http://127.0.0.1:8000/docs, call `POST /login` with the first manager's username
(set in `database.py`) and password, copy the token, click **Authorize** and paste it:
from then on every endpoint can be tried from the browser.
The database file is created automatically on the first run.

## Tests

```bash
pip install pytest
pytest
```

The tests run on a separate database, recreated before every test by a pytest fixture,
so each test starts from known data and never touches the real one. They cover the
normal cases and the edge ones: missing, invalid and expired tokens, wrong role,
validation errors, missing resources, deletion of items and users with movements.

## Roadmap

- [x] Movement history with filters (by operator, type, date)
- [x] Block the deletion of items and users that have movements (`409`)
- [x] Automated tests (pytest)
- [x] Login with session tokens and hashed passwords
- [x] Roles (operator / manager)
- [x] Authentication as FastAPI dependencies (`Depends` + `HTTPBearer`)
- [ ] Operator role check as a dependency too (manager check already done)
- [ ] Database connection as a `yield` dependency (one connection per request, closed automatically)
- [ ] `requirements.txt`
- [ ] Record the initial stock of a new item as a movement
- [ ] Migration to SQLAlchemy, then PostgreSQL and Docker

## Tech stack

Python · FastAPI · Pydantic · SQLite · pwdlib (Argon2) · python-dotenv · pytest
