from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from app.database import UtenteORM, SessionDep
from app.schemas import Utente
from app.security import controlla_ruolo_responsabile, password_hash
from app.dependencies import controlla_utente
from sqlalchemy import select

router = APIRouter(prefix="/utenti", tags=["UTENTI"])

@router.post("")
def nuovo_utente(session: SessionDep, nuovo: Utente, id_responsabile: int = Depends(controlla_ruolo_responsabile)):
    username = nuovo.username.lower()
    query_utente = select(UtenteORM).where(UtenteORM.username == username)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is not None:
        raise HTTPException(status_code=409, detail="Username gia presente")
    ruolo = nuovo.ruolo.lower()
    if ruolo not in ["addetto", "responsabile"]:
        raise HTTPException(status_code=400, detail="Inserire addetto o responsabile")
    hash_utente = password_hash.hash(nuovo.password)
    nuovo_utente = UtenteORM(nome = nuovo.nome, hash_utente = hash_utente, username = username, ruolo = ruolo)
    session.add(nuovo_utente)
    session.commit()
    return {"id_utente": nuovo_utente.id, "nome": nuovo_utente.nome, "username": nuovo_utente.username, "ruolo": nuovo_utente.ruolo}


@router.get("")
def mostra_utenti(session: SessionDep, id_responsabile: int = Depends(controlla_ruolo_responsabile)):
    query_utenti = select(UtenteORM)
    utenti_trovati = session.scalars(query_utenti).all()
    lista_utenti = []
    for utente in utenti_trovati:
        utente_singolo = {"nome": utente.nome, "id": utente.id, "ruolo": utente.ruolo, "username": utente.username}
        lista_utenti.append(utente_singolo)
    return lista_utenti


@router.get("/{id_utente}")
def cerca_utente(id_responsabile: int = Depends(controlla_ruolo_responsabile), utente: UtenteORM = Depends(controlla_utente)):
    return {"nome": utente.nome, "id": utente.id, "ruolo": utente.ruolo, "username": utente.username}


@router.delete("/{id_utente}")
def rimuovi_utente(session: SessionDep, id_responsabile: int = Depends(controlla_ruolo_responsabile), utente: UtenteORM = Depends(controlla_utente)):
    if utente.movimenti:
        raise HTTPException(status_code=409, detail="L'utente presenta movimenti")
    session.delete(utente)
    session.commit()
    return {"utente_eliminato": {"nome": utente.nome, "id": utente.id, "ruolo": utente.ruolo, "username": utente.username}}