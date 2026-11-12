from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from app.schemas import Articolo, ModificaArticolo, CaricoPrelievo
from app.database import ArticoloORM, MovimentoORM, spacchetta_articolo, spacchetta_movimento, apri_db, controlla_articolo, crea_movimento
from app.security import controlla_ruolo_responsabile, controlla_ruolo_addetto_responsabile
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime


router = APIRouter(prefix="/catalogo", tags=["CATALOGO"])


@router.post("")
def aggiungi_articolo(articolo: Articolo, id_utente_movimento: int = Depends(controlla_ruolo_addetto_responsabile), session: Session = Depends(apri_db)):
    data_movimento = str(datetime.now().replace(microsecond=0))
    nuovo_articolo = ArticoloORM(nome = articolo.nome, prezzo = articolo.prezzo, categoria = articolo.categoria.lower(), quantita = articolo.quantita, data_inserimento = data_movimento, data_ultimo_movimento = data_movimento)
    nuovo_movimento = MovimentoORM(id_utente = id_utente_movimento, articolo = nuovo_articolo, quantita = nuovo_articolo.quantita, tipo = "nuovo articolo", data = data_movimento, giacenza_dopo_movimento = nuovo_articolo.quantita)
    session.add_all([nuovo_articolo, nuovo_movimento])
    session.commit()
    return {"articolo": spacchetta_articolo(nuovo_articolo), "movimento": spacchetta_movimento(nuovo_movimento)}


@router.get("")
def trova_prodotti(prezzo_inferiore_a: float = None, categoria: str = None, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), session: Session = Depends(apri_db)):
    query_catalogo = select(ArticoloORM)
    if categoria is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.categoria == categoria.lower())
    if prezzo_inferiore_a is not None:
        query_catalogo = query_catalogo.where(ArticoloORM.prezzo <= prezzo_inferiore_a)
    catalogo_trovato = session.scalars(query_catalogo).all()
    lista_articoli = []
    for articolo in catalogo_trovato:
        articolo_spacchettato = spacchetta_articolo(articolo)
        lista_articoli.append(articolo_spacchettato)
    return lista_articoli


@router.get("/{id_prodotto}")
def cerca_id(id_utente: int = Depends(controlla_ruolo_addetto_responsabile), prodotto: ArticoloORM = Depends(controlla_articolo)):
    return spacchetta_articolo(prodotto)


@router.delete("/{id_prodotto}")
def rimuovi_prodotto(id_responsabile: int = Depends(controlla_ruolo_responsabile), prodotto: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    for movimento in prodotto.movimenti:
        if movimento.tipo != "nuovo articolo":
            raise HTTPException(status_code=409, detail="L'articolo presenta movimenti")
        else:
            session.delete(movimento)
    session.delete(prodotto)
    session.commit()
    return spacchetta_articolo(prodotto)


@router.patch("/{id_prodotto}")
def modifica_articolo(nuovo: ModificaArticolo, id_responsabile: int = Depends(controlla_ruolo_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    if nuovo.nome is not None:
        articolo.nome= nuovo.nome
    if nuovo.prezzo is not None:
        articolo.prezzo = nuovo.prezzo
    if nuovo.categoria is not None:
        articolo.categoria = nuovo.categoria.lower()
    session.commit()
    return spacchetta_articolo(articolo)


@router.patch("/{id_prodotto}/carico")
def carica_quantita_articolo(richiesta: CaricoPrelievo, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    data_movimento = str(datetime.now().replace(microsecond=0))
    articolo.quantita += richiesta.quantita
    articolo.data_ultimo_movimento = data_movimento
    nuovo_movimento = crea_movimento(id_utente, articolo.id, richiesta.quantita, "carico", data_movimento, articolo.quantita)
    session.add(nuovo_movimento)
    session.commit()
    return {"articolo": spacchetta_articolo(articolo), "movimento" : spacchetta_movimento(nuovo_movimento)}

@router.patch("/{id_prodotto}/prelievo")
def preleva_merce(richiesta: CaricoPrelievo, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
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
    return {"articolo": spacchetta_articolo(articolo), "movimento": spacchetta_movimento(nuovo_movimento), "da_prelevare": rimanenza}


@router.get("/{id_prodotto}/movimenti")
def movimenti_articolo(data: str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    query_articolo = select(MovimentoORM).where(MovimentoORM.id_articolo == articolo.id)
    if data is not None:
        query_articolo = query_articolo.where(MovimentoORM.data.startswith(data))
    articolo_movimenti = session.scalars(query_articolo).all()
    lista_movimenti = []
    for movimento in articolo_movimenti:
        lista_movimenti.append(spacchetta_movimento(movimento))
    return lista_movimenti