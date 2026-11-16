from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from sqlalchemy import select
from app.security import ResponsabileDep
from app.database import MovimentoORM, SessionDep
from app.dependencies import  UtenteDep
from app.schemas import MovimentoOut, MovimentoCompletoOut

router = APIRouter(prefix="/movimenti", tags=["MOVIMENTI"])


@router.get("", response_model=list[MovimentoCompletoOut])
def movimenti_completo(id_responsabile: ResponsabileDep, session: SessionDep, data : str = None):
    query_movimenti = select(MovimentoORM)
    if data is not None:
        query_movimenti = query_movimenti.where(MovimentoORM.data.startswith(data))
    movimenti = session.scalars(query_movimenti).all()
    return movimenti

@router.get("/{id_utente}", response_model=list[MovimentoOut])
def movimenti_utente(id_responsabile: ResponsabileDep, utente: UtenteDep, session: SessionDep, tipo_movimenti: str = None, data: str = None):
    query_movimenti = select(MovimentoORM).where(MovimentoORM.id_utente == utente.id)
    if tipo_movimenti is not None:
        if tipo_movimenti not in ["carico", "prelievo", "nuovo articolo"]:
            raise HTTPException(status_code=400, detail="Tipo movimento non valido")
        query_movimenti = query_movimenti.where(MovimentoORM.tipo == tipo_movimenti)
    if data is not None:
        query_movimenti = query_movimenti.where(MovimentoORM.data.startswith(data))
    movimenti = session.scalars(query_movimenti).all()
    return movimenti
