from fastapi import FastAPI
from app.routers import catalogo, utenti, movimenti, login
from app.security import password_hash
from app.seed import inserisci_seed

app = FastAPI()

app.include_router(utenti.router)
app.include_router(catalogo.router)
app.include_router(movimenti.router)
app.include_router(login.router)

inserisci_seed()