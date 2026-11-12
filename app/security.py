from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends
from fastapi.exceptions import HTTPException
from app.database import apri_db, SessioneORM, UtenteORM
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

schema_bearer = HTTPBearer()


def controlla_token(credenziali: HTTPAuthorizationCredentials = Depends(schema_bearer), session: Session = Depends(apri_db)):
    token = credenziali.credentials
    query_sessione = select(SessioneORM).where(SessioneORM.token == token)
    sessione_trovata = session.scalars(query_sessione).one_or_none()
    if sessione_trovata is None:
        raise HTTPException(status_code=401, detail="Token non valido")
    scadenza = datetime.fromisoformat(sessione_trovata.scadenza)
    if scadenza > datetime.now().replace(microsecond=0):
        return sessione_trovata.id_utente
    else:
        raise HTTPException(status_code=401, detail="Token scaduto")


def controlla_ruolo_addetto_responsabile(id_utente: int = Depends(controlla_token), session: Session = Depends(apri_db)):
    query_utente = select(UtenteORM).where(UtenteORM.id == id_utente)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is not None:
        if utente_trovato.ruolo not in ["addetto", "responsabile"]:
            raise HTTPException(status_code=403, detail="Azione negata")
        else:
            return id_utente
    else:
        raise HTTPException(status_code=401, detail="Utente non trovato")


def controlla_ruolo_responsabile(id_utente: int = Depends(controlla_token), session: Session = Depends(apri_db)):
    query_responsabile = select(UtenteORM).where(UtenteORM.id == id_utente)
    responsabile_trovato = session.scalars(query_responsabile).one_or_none()
    if responsabile_trovato is not None:
        if responsabile_trovato.ruolo != "responsabile":
            raise HTTPException(status_code=403, detail="Azione negata")
        else:
            return id_utente
    else:
        raise HTTPException(status_code=401, detail="Utente non trovato")