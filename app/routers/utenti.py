from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException
from app.database import UtenteORM, SessionDep
from app.schemas import Utente, UtenteOut, ModificaUtente
from app.security import password_hash, ResponsabileDep
from app.dependencies import UtenteDep
from sqlalchemy import select

router = APIRouter(prefix="/utenti", tags=["UTENTI"])

@router.post("", response_model=UtenteOut, status_code=status.HTTP_201_CREATED)
def nuovo_utente(id_responsabile: ResponsabileDep, session: SessionDep, nuovo: Utente):
    username = nuovo.username.lower()
    query_utente = select(UtenteORM).where(UtenteORM.username == username)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username gia presente")
    ruolo = nuovo.ruolo.lower()
    if ruolo not in ["addetto", "responsabile"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inserire addetto o responsabile")
    hash_utente = password_hash.hash(nuovo.password)
    nuovo_utente = UtenteORM(nome = nuovo.nome.capitalize(), hash_utente = hash_utente, username = username, ruolo = ruolo)
    session.add(nuovo_utente)
    session.commit()
    return nuovo_utente


@router.get("", response_model=list[UtenteOut])
def mostra_utenti(id_responsabile: ResponsabileDep, session: SessionDep):
    query = select(UtenteORM)
    utenti_trovati = session.scalars(query).all()
    return utenti_trovati


@router.get("/{id_utente}", response_model=UtenteOut)
def cerca_utente(id_responsabile: ResponsabileDep, utente: UtenteDep):
    return utente


@router.delete("/{id_utente}", response_model=UtenteOut)
def rimuovi_utente(id_responsabile: ResponsabileDep, utente: UtenteDep, session: SessionDep):
    if utente.movimenti:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="L'utente presenta movimenti")
    session.delete(utente)
    session.commit()
    return utente


@router.patch("/{id_utente}", response_model=UtenteOut)
def modifica_utente(responsabile: ResponsabileDep, utente: UtenteDep, session: SessionDep, nuovo: ModificaUtente):
    for field, value in nuovo.model_dump(exclude_unset=True).items():
        if not value:
            continue
        if field == "ruolo":
            value = value.lower()
            if value not in ["addetto", "responsabile"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inserire addetto o responsabile")
        if field == "nome":
            value = value.capitalize()
        if field == "username":
            value = value.lower()
            query = select(UtenteORM).where(UtenteORM.username == value)
            utente_trovato = session.scalars(query).one_or_none()
            if utente_trovato is not None:
                    if utente_trovato.id != utente.id:
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username gia in uso")
        setattr(utente, field, value)
    session.commit()
    return utente