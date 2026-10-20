# Warehouse Management API

A small warehouse management backend built with **FastAPI** and **SQLite**, designed around
the problems I saw every day in 10 years of warehouse work: stock that doesn't add up,
pickings that can't be traced back to an operator, and history that gets lost.

> **Status: work in progress.** Version 1 (items, loading, picking) is complete.
> Version 2 (operators and stock movement history) is being built right now.

## What it does

- **Items catalogue**: create, list (with filters by category and max price), read, update and delete items
- **Loading and picking**: add or remove stock from an item
- **Operators**: create the users who move the goods
- **Movement history**: every loading and picking is recorded with *who*, *what*, *how many*, *when*
  and the *stock left after the movement*
- **Manager view**: a single endpoint that returns the full history with operator and item names
- **Operator report**: all movements of one operator, filterable by type and day, with the total pieces loaded and picked

## Design choices

These are the decisions I'm most interested in, because they come from real warehouse situations:

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
- **All-or-nothing writes.** Stock update and movement record are committed together,
  once, at the end of the request: if one of the two fails, nothing is saved.
- **Code split in two files**: `database.py` holds the connection, the tables and the helper
  functions (checks, row unpacking, movement creation); `gestionale.py` holds only the endpoints.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/catalogo` | Add a new item |
| `GET` | `/catalogo` | List items, optional filters `categoria` and `prezzo_inferiore_a` |
| `GET` | `/catalogo/{id_prodotto}` | Read one item (404 if missing) |
| `PATCH` | `/catalogo/{id_prodotto}` | Update name, price or category |
| `DELETE` | `/catalogo/{id_prodotto}` | Delete an item |
| `PATCH` | `/catalogo/{id_prodotto}/carico` | Load stock (records a movement) |
| `PATCH` | `/catalogo/{id_prodotto}/prelievo` | Pick stock (records a movement, reports missing pieces) |
| `POST` | `/utenti` | Add an operator |
| `GET` | `/utenti` | List all operators |
| `GET` | `/movimenti` | Full movement history with operator and item names (SQL `JOIN`), optional filter `data` (YYYY-MM-DD) |
| `GET` | `/movimenti/{id_utente}` | Movements of one operator, optional filters `tipo_movimenti` (`carico` / `prelievo`) and `data`, with loaded and picked totals (404 if the operator doesn't exist, 400 if the type is not valid) |

## Database

Three tables in SQLite:

- `articoli`: id, name, price, category, quantity, insertion date, last movement date
- `utenti`: id, name
- `movimenti`: id, operator id, item id, quantity, type (`carico` / `prelievo`), date, stock after movement

## Run it locally

```bash
pip install "fastapi[standard]"
fastapi dev gestionale.py
```

Then open http://127.0.0.1:8000/docs to try every endpoint from the browser.
The database file is created automatically on the first run.

## Roadmap

- [ ] Decide how to handle the deletion of an item that already has movements
      (block it with a clear message, or mark the item as inactive)
- [x] `GET /utenti`
- [ ] Roles (operator / manager)
- [x] Filters on the movement history (by operator, type, date)
- [ ] Record the initial stock of a new item as a movement
- [ ] Filters on the movement history (by operator, item, date)
- [ ] Automated tests
- [ ] Migration to SQLAlchemy, then PostgreSQL and Docker

## Tech stack

Python · FastAPI · Pydantic · SQLite
