from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy import select
from app.security import controlla_ruolo_responsabile
from app.database import MovimentoORM, UtenteORM, spacchetta_movimenti_completo, spacchetta_movimento, SessionDep
from app.dependencies import controlla_utente

router = APIRouter(prefix="/movimenti", tags=["MOVIMENTI"])


@router.get("")
def movimenti_completo(session: SessionDep, data : str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile)):
    query_movimenti = select(MovimentoORM)
    if data is not None:
        query_movimenti = query_movimenti.where(MovimentoORM.data.startswith(data))
    movimenti = session.scalars(query_movimenti).all()
    lista_movimenti = []
    for movimento in movimenti:
        movimento_trovato = spacchetta_movimenti_completo(movimento)
        lista_movimenti.append(movimento_trovato)
    return lista_movimenti

@router.get("/{id_utente}")
def movimenti_utente(session: SessionDep, tipo_movimenti: str = None, data: str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), utente: UtenteORM = Depends(controlla_utente)):
    query_movimenti = select(MovimentoORM).where(MovimentoORM.id_utente == utente.id)
    if tipo_movimenti is not None:
        if tipo_movimenti not in ["carico", "prelievo", "nuovo articolo"]:
            raise HTTPException(status_code=400, detail="Tipo movimento non valido")
        query_movimenti = query_movimenti.where(MovimentoORM.tipo == tipo_movimenti)
    if data is not None:
        query_movimenti = query_movimenti.where(MovimentoORM.data.startswith(data))
    movimenti = session.scalars(query_movimenti).all()
    lista_movimenti = []
    for movimento in movimenti:
        movimento_trovato = spacchetta_movimento(movimento)
        lista_movimenti.append(movimento_trovato)
    return lista_movimenti
