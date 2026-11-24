from fastapi import APIRouter, status, Query
from fastapi.exceptions import HTTPException
from app.schemas import Articolo, ModificaArticolo, CaricoPrelievo, MovimentoOut, ArticoloConMovimento, ArticoloOut, ArticoloPrelevatoOut, FiltriCatalogo, CatalogoOut
from app.database import ArticoloORM, MovimentoORM, SessionDep
from app.security import ResponsabileDep, AddettoDep
from app.dependencies import ArticoloDep
from sqlalchemy import select
from datetime import datetime
from typing import Annotated


router = APIRouter(prefix="/catalogo", tags=["CATALOGO"])


def crea_movimento(id_utente_movimento, id_articolo_movimento, quantita_movimento, tipo_movimento, data_movimento, giacenza_post):
    nuovo_movimento = MovimentoORM(id_utente = id_utente_movimento, id_articolo = id_articolo_movimento, quantita = quantita_movimento, tipo = tipo_movimento, data = data_movimento, giacenza_dopo_movimento = giacenza_post)
    return nuovo_movimento


@router.post("", response_model=ArticoloConMovimento, status_code=status.HTTP_201_CREATED)
def aggiungi_articolo(id_utente_movimento: AddettoDep, session: SessionDep, articolo: Articolo):
    data_movimento = str(datetime.now().replace(microsecond=0))
    dati_articolo = articolo.model_dump()
    dati_articolo["categoria"] = dati_articolo["categoria"].lower()
    nuovo_articolo = ArticoloORM(**dati_articolo, data_inserimento = data_movimento, data_ultimo_movimento = data_movimento)
    nuovo_movimento = MovimentoORM(id_utente = id_utente_movimento, articolo = nuovo_articolo, quantita = nuovo_articolo.quantita, tipo = "nuovo articolo", data = data_movimento, giacenza_dopo_movimento = nuovo_articolo.quantita)
    session.add_all([nuovo_articolo, nuovo_movimento])
    session.commit()
    return {"articolo": nuovo_articolo, "movimento": nuovo_movimento}


@router.get("", response_model=CatalogoOut)
def trova_prodotti(id_utente: AddettoDep, session: SessionDep, filtri: Annotated[FiltriCatalogo, Query()]):
    query_catalogo = select(ArticoloORM)
    if filtri.categoria is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.categoria == filtri.categoria.lower())
    if filtri.prezzo_massimo is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.prezzo <= filtri.prezzo_massimo)
    if filtri.data_inserimento is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.data_inserimento.startswith(filtri.data_inserimento))
    if filtri.nome is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.nome.ilike(f"%{filtri.nome}%"))
    if filtri.quantita_massima is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.quantita <= filtri.quantita_massima)
    catalogo_trovato = session.scalars(query_catalogo).all()
    return {"articoli": catalogo_trovato, "totale": len(catalogo_trovato)}


@router.get("/{id_prodotto}", response_model=ArticoloOut)
def cerca_id(prodotto: ArticoloDep, id_utente: AddettoDep):
    return prodotto


@router.delete("/{id_prodotto}", response_model=ArticoloOut)
def rimuovi_prodotto(id_responsabile: ResponsabileDep, prodotto: ArticoloDep, session: SessionDep):
    for movimento in prodotto.movimenti:
        if movimento.tipo != "nuovo articolo":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="L'articolo presenta movimenti")
        else:
            session.delete(movimento)
    session.delete(prodotto)
    session.commit()
    return prodotto


@router.patch("/{id_prodotto}", response_model=ArticoloOut)
def modifica_articolo(id_responsabile: ResponsabileDep, articolo: ArticoloDep, session: SessionDep, nuovo: ModificaArticolo):
    for field, value in nuovo.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if field == "categoria":
            value = value.lower()
        setattr(articolo, field, value)
    session.commit()
    return articolo


@router.patch("/{id_prodotto}/carico", response_model=ArticoloConMovimento)
def carica_quantita_articolo(id_utente: AddettoDep,articolo: ArticoloDep, session: SessionDep, richiesta: CaricoPrelievo):
    data_movimento = str(datetime.now().replace(microsecond=0))
    articolo.quantita += richiesta.quantita
    articolo.data_ultimo_movimento = data_movimento
    nuovo_movimento = crea_movimento(id_utente, articolo.id, richiesta.quantita, "carico", data_movimento, articolo.quantita)
    session.add(nuovo_movimento)
    session.commit()
    return {"articolo": articolo, "movimento" : nuovo_movimento}

@router.patch("/{id_prodotto}/prelievo", response_model=ArticoloPrelevatoOut)
def preleva_merce(id_utente: AddettoDep,session: SessionDep, richiesta: CaricoPrelievo, articolo: ArticoloDep):
    data_movimento = str(datetime.now().replace(microsecond=0))
    if richiesta.quantita >= articolo.quantita:
        rimanenza = richiesta.quantita - articolo.quantita
        quantita_movimento = articolo.quantita
        articolo.quantita = 0
    else:
        articolo.quantita -= richiesta.quantita
        quantita_movimento = richiesta.quantita
        rimanenza = 0
    articolo.data_ultimo_movimento = data_movimento
    nuovo_movimento = crea_movimento(id_utente, articolo.id, quantita_movimento, "prelievo", data_movimento, articolo.quantita)
    session.add(nuovo_movimento)
    session.commit()
    return {"articolo": articolo, "movimento": nuovo_movimento, "da_prelevare": rimanenza}


@router.get("/{id_prodotto}/movimenti", response_model=list[MovimentoOut])
def movimenti_articolo(id_responsabile: ResponsabileDep, articolo: ArticoloDep, session: SessionDep, data: str = None):
    query_articolo = select(MovimentoORM).where(MovimentoORM.id_articolo == articolo.id)
    if data is not None:
        query_articolo = query_articolo.where(MovimentoORM.data.startswith(data))
    articolo_movimenti = session.scalars(query_articolo).all()
    return articolo_movimenti