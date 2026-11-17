from fastapi import FastAPI
from app.routers import catalogo, utenti, movimenti, login
from app.seed import inserisci_seed
from app.database import Base, engine
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    inserisci_seed()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(utenti.router)
app.include_router(catalogo.router)
app.include_router(movimenti.router)
app.include_router(login.router)