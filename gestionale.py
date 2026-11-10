from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import spacchetta_articolo, controlla_articolo, controlla_utente, crea_movimento, spacchetta_movimenti_completo, controlla_ruolo_addetto_responsabile, controlla_ruolo_responsabile, apri_db, spacchetta_movimento, UtenteORM, ArticoloORM, MovimentoORM, SessioneORM
import secrets
from pwdlib import PasswordHash
password_hash = PasswordHash.recommended()

app = FastAPI()

class Articolo(BaseModel):
    nome: str = Field(min_length = 2)
    prezzo: float = Field(gt = 0)
    categoria: str = Field(min_length = 2)
    quantita: int = Field(gt = 0)

class ModificaArticolo(BaseModel):
    nome: str | None = Field(default = None, min_length = 2)
    prezzo: float | None = Field(default = None, gt = 0)
    categoria: str | None = Field(default = None, min_length = 2)

class CaricoPrelievo(BaseModel):
    quantita: int = Field(gt = 0)

class Utente(BaseModel):
    nome: str = Field(min_length = 2)
    username: str = Field(min_length=3, max_length=15)
    ruolo: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length = 8)

class LoginUtente(BaseModel):
    username: str 
    password: str 

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

@app.post("/utenti", tags=["UTENTI"])
def nuovo_utente(nuovo: Utente, id_responsabile: int = Depends(controlla_ruolo_responsabile), session: Session = Depends(apri_db)):
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

@app.post("/catalogo", tags=["CATALOGO"])
def aggiungi_articolo(articolo: Articolo, id_utente_movimento: int = Depends(controlla_ruolo_addetto_responsabile), session: Session = Depends(apri_db)):
    data_movimento = str(datetime.now().replace(microsecond=0))
    nuovo_articolo = ArticoloORM(nome = articolo.nome, prezzo = articolo.prezzo, categoria = articolo.categoria.lower(), quantita = articolo.quantita, data_inserimento = data_movimento, data_ultimo_movimento = data_movimento)
    nuovo_movimento = MovimentoORM(id_utente = id_utente_movimento, articolo = nuovo_articolo, quantita = nuovo_articolo.quantita, tipo = "nuovo articolo", data = data_movimento, giacenza_dopo_movimento = nuovo_articolo.quantita)
    session.add_all([nuovo_articolo, nuovo_movimento])
    session.commit()
    return {"articolo": spacchetta_articolo(nuovo_articolo), "movimento": spacchetta_movimento(nuovo_movimento)}

@app.get("/catalogo", tags=["CATALOGO"])
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

@app.get("/catalogo/{id_prodotto}", tags=["CATALOGO"])
def cerca_id(id_utente: int = Depends(controlla_ruolo_addetto_responsabile), prodotto: ArticoloORM = Depends(controlla_articolo)):
    return spacchetta_articolo(prodotto)

@app.delete("/catalogo/{id_prodotto}", tags=["CATALOGO"])
def rimuovi_prodotto(id_responsabile: int = Depends(controlla_ruolo_responsabile), prodotto: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    for movimento in prodotto.movimenti:
        if movimento.tipo != "nuovo articolo":
            raise HTTPException(status_code=409, detail="L'articolo presenta movimenti")
        else:
            session.delete(movimento)
    session.delete(prodotto)
    session.commit()
    return spacchetta_articolo(prodotto)

@app.patch("/catalogo/{id_prodotto}", tags=["CATALOGO"])
def modifica_articolo(nuovo: ModificaArticolo, id_responsabile: int = Depends(controlla_ruolo_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    if nuovo.nome is not None:
        articolo.nome= nuovo.nome
    if nuovo.prezzo is not None:
        articolo.prezzo = nuovo.prezzo
    if nuovo.categoria is not None:
        articolo.categoria = nuovo.categoria.lower()
    session.commit()
    return spacchetta_articolo(articolo)

@app.patch("/catalogo/{id_prodotto}/carico", tags=["CARICA/PRELEVA"])
def carica_quantita_articolo(richiesta: CaricoPrelievo, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    data_movimento = str(datetime.now().replace(microsecond=0))
    articolo.quantita += richiesta.quantita
    articolo.data_ultimo_movimento = data_movimento
    nuovo_movimento = crea_movimento(id_utente, articolo.id, richiesta.quantita, "carico", data_movimento, articolo.quantita)
    session.add(nuovo_movimento)
    session.commit()
    return {"articolo": spacchetta_articolo(articolo), "movimento" : spacchetta_movimento(nuovo_movimento)}

@app.patch("/catalogo/{id_prodotto}/prelievo", tags=["CARICA/PRELEVA"])
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

@app.get("/movimenti", tags=["MOVIMENTI"])
def movimenti_completo(data : str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), session: Session = Depends(apri_db)):
    query_movimenti = select(MovimentoORM)
    if data is not None:
        query_movimenti = query_movimenti.where(MovimentoORM.data.startswith(data))
    movimenti = session.scalars(query_movimenti).all()
    lista_movimenti = []
    for movimento in movimenti:
        movimento_trovato = spacchetta_movimenti_completo(movimento)
        lista_movimenti.append(movimento_trovato)
    return lista_movimenti

@app.get("/movimenti/{id_utente}", tags=["MOVIMENTI"])
def movimenti_utente(tipo_movimenti: str = None, data: str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), utente: UtenteORM = Depends(controlla_utente), session: Session = Depends(apri_db)):
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

@app.get("/catalogo/{id_prodotto}/movimenti", tags=["MOVIMENTI"])
def movimenti_articolo(data: str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), articolo: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    query_articolo = select(MovimentoORM).where(MovimentoORM.id_articolo == articolo.id)
    if data is not None:
        query_articolo = query_articolo.where(MovimentoORM.data.startswith(data))
    articolo_movimenti = session.scalars(query_articolo).all()
    lista_movimenti = []
    for movimento in articolo_movimenti:
        lista_movimenti.append(spacchetta_movimento(movimento))
    return lista_movimenti

@app.get("/utenti", tags=["UTENTI"])
def mostra_utenti(id_responsabile: int = Depends(controlla_ruolo_responsabile), session: Session = Depends(apri_db)):
    query_utenti = select(UtenteORM)
    utenti_trovati = session.scalars(query_utenti).all()
    lista_utenti = []
    for utente in utenti_trovati:
        utente_singolo = {"nome": utente.nome, "id": utente.id, "ruolo": utente.ruolo, "username": utente.username}
        lista_utenti.append(utente_singolo)
    return lista_utenti

@app.get("/utenti/{id_utente}", tags=["UTENTI"])
def cerca_utente(id_responsabile: int = Depends(controlla_ruolo_responsabile), utente: UtenteORM = Depends(controlla_utente), session: Session = Depends(apri_db)):
    return {"nome": utente.nome, "id": utente.id, "ruolo": utente.ruolo, "username": utente.username}

@app.delete("/utenti/{id_utente}", tags=["UTENTI"])
def rimuovi_utente(id_responsabile: int = Depends(controlla_ruolo_responsabile), utente: UtenteORM = Depends(controlla_utente), session: Session = Depends(apri_db)):
    if utente.movimenti:
        raise HTTPException(status_code=409, detail="L'utente presenta movimenti")
    session.delete(utente)
    session.commit()
    return {"utente_eliminato": {"nome": utente.nome, "id": utente.id, "ruolo": utente.ruolo, "username": utente.username}}