from app.database import SessionDep, ArticoloORM, UtenteORM
from fastapi.exceptions import HTTPException
from sqlalchemy import select


def controlla_articolo(session: SessionDep, id_prodotto: int):
    query_prodotto = select(ArticoloORM).where(ArticoloORM.id == id_prodotto)
    articolo_trovato = session.scalars(query_prodotto).one_or_none()
    if articolo_trovato is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return articolo_trovato


def controlla_utente(session: SessionDep, id_utente: int):
    query_utente = select(UtenteORM).where(UtenteORM.id == id_utente)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return utente_trovato
