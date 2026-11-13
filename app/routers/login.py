from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from app.database import UtenteORM, SessioneORM, SessionDep
from app.schemas import LoginUtente 
from app.security import password_hash
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets


router = APIRouter(prefix=("/login"), tags=["LOGIN"])

@router.post("")
def login_utente(session: SessionDep, utente: LoginUtente):
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