from fastapi import FastAPI, HTTPException, Depends
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.routers import catalogo, utenti
from app.database import apri_db, UtenteORM,  SessioneORM
from app.schemas import LoginUtente
import secrets
from app.routers import movimenti
from app.security import password_hash
from app.seed import inserisci_seed

app = FastAPI()

app.include_router(utenti.router)
app.include_router(catalogo.router)
app.include_router(movimenti.router)



@app.post("/login", tags=["LOGIN"])
def login_utente(utente: LoginUtente, session: Session = Depends(apri_db)):
    username = utente.username.lower()
    query_utente = select(UtenteORM).where(UtenteORM.username == username)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is None:
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    verifica_hash = password_hash.verify(utente.password, utente_trovato.hash_utente)
    if verifica_hash:
        token_utente = secrets.token_urlsafe(32)
        scadenza_token = datetime.now().replace(microsecond=0) + timedelta(hours=8)
        nuova_sessione = SessioneORM(utente = utente_trovato, token = token_utente, scadenza = str(scadenza_token))
        session.add(nuova_sessione)
        session.commit()
        return {"token": token_utente}
    else:
        raise HTTPException(401, detail="Credenziali non valide")


inserisci_seed()