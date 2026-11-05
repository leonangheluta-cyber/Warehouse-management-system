from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import sqlite3
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import spacchetta_articolo, controlla_articolo, controlla_utente, crea_movimento, spacchetta_movimenti_completo, controlla_movimento_prodotto, controlla_movimento_utente, controlla_token, controlla_ruolo_addetto_responsabile, controlla_ruolo_responsabile, apri_db, UtenteORM, ArticoloORM, MovimentoORM, SessioneORM
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

@app.post("/utenti")
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
    return {"ID utente": nuovo_utente.id, "Nome": nuovo_utente.nome, "Username": nuovo_utente.username, "Ruolo": nuovo_utente.ruolo}

@app.post("/login")
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

@app.post("/catalogo")
def aggiungi_articolo(articolo: Articolo, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), session: Session = Depends(apri_db)):
    data = str(datetime.now().replace(microsecond=0))
    nuovo_articolo = ArticoloORM(nome = articolo.nome, prezzo = articolo.prezzo, categoria = articolo.categoria, quantita = articolo.quantita, data_inserimento = data, data_ultimo_movimento = data)
    session.add(nuovo_articolo)
    session.commit()
    return spacchetta_articolo(nuovo_articolo)

@app.get("/catalogo")
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

@app.get("/catalogo/{id_prodotto}")
def cerca_id(id_utente: int = Depends(controlla_ruolo_addetto_responsabile), prodotto: ArticoloORM = Depends(controlla_articolo)):
    return spacchetta_articolo(prodotto)

@app.delete("/catalogo/{id_prodotto}")
def rimuovi_prodotto(id_responsabile: int = Depends(controlla_ruolo_responsabile), prodotto: ArticoloORM = Depends(controlla_articolo), session: Session = Depends(apri_db)):
    if not prodotto.movimenti:
        session.delete(prodotto)
        session.commit()
    else:
        raise HTTPException(status_code=409, detail="L'articolo presenta movimenti")
    return spacchetta_articolo(prodotto)

@app.patch("/catalogo/{id_prodotto}")
def modifica_articolo(articolo: ModificaArticolo, id_prodotto: int, id_responsabile: int = Depends(controlla_ruolo_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    controlla_articolo(conn, id_prodotto,)
    conn.execute("UPDATE articoli SET nome = coalesce(?, nome), prezzo = coalesce(?, prezzo), categoria = coalesce(?, categoria) WHERE id = ?", (articolo.nome, articolo.prezzo, articolo.categoria, id_prodotto))
    cursore_aggiornato = conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato = cursore_aggiornato.fetchone()
    conn.commit()
    prodotto_finale = spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/carico")
def carica_quantita_articolo(richiesta: CaricoPrelievo, id_prodotto: int, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    data = str(datetime.now().replace(microsecond = 0))
    controlla_articolo(conn, id_prodotto,)
    controlla_utente(conn, id_utente)
    conn.execute("""UPDATE articoli SET quantita = quantita + ?, data_ultimo_movimento = ? WHERE id = ?""", (richiesta.quantita, data, id_prodotto))
    cursore_aggiornato = conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato = cursore_aggiornato.fetchone()
    giacenza_aggiornata = prodotto_aggiornato[4]
    movimento = crea_movimento(conn, id_utente, id_prodotto, richiesta.quantita, "carico", giacenza_aggiornata)
    conn.commit()
    prodotto_finale = spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale, movimento

@app.patch("/catalogo/{id_prodotto}/prelievo")
def preleva_merce(richiesta: CaricoPrelievo, id_prodotto: int, id_utente: int = Depends(controlla_ruolo_addetto_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    data = str(datetime.now().replace(microsecond = 0))
    riga = controlla_articolo(conn, id_prodotto)
    controlla_utente(conn, id_utente)
    quantita_prodotto_attuale = riga[4]
    if richiesta.quantita<quantita_prodotto_attuale:
        quantita_prelevata = richiesta.quantita
    else:
        quantita_prelevata = quantita_prodotto_attuale
    conn.execute("""UPDATE articoli SET
        quantita = CASE WHEN ? <= quantita THEN quantita - ? WHEN ? > quantita THEN 0 END,
        data_ultimo_movimento = ?  WHERE id = ?""", (richiesta.quantita, richiesta.quantita, richiesta.quantita, data, id_prodotto))
    cursore_aggiornato = conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato = cursore_aggiornato.fetchone()
    giacenza_finale = prodotto_aggiornato[4]
    movimento = crea_movimento(conn, id_utente, id_prodotto, quantita_prelevata, "prelievo", giacenza_finale)
    conn.commit()
    prodotto_finale = spacchetta_riga_articolo(prodotto_aggiornato)
    if richiesta.quantita>quantita_prodotto_attuale:
        calcolo_prelievo = richiesta.quantita-quantita_prodotto_attuale
        prodotto_finale["mancanti"] = calcolo_prelievo
        return prodotto_finale, movimento
    prodotto_finale["mancanti"] = 0
    return prodotto_finale, movimento

@app.get("/movimenti")
def movimenti_completo(data : str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    cursore = conn.execute("""SELECT movimenti.id, utenti.id, utenti.nome, movimenti.quantita, movimenti.tipo, articoli.nome, movimenti.giacenza_dopo_movimento, movimenti.data FROM movimenti
                            LEFT JOIN utenti on movimenti.id_utente = utenti.id
                            LEFT JOIN articoli on movimenti.id_articolo = articoli.id""")
    movimenti = cursore.fetchall()
    lista_movimenti = []
    for riga in movimenti:
        if data is None or data == riga[7][:10]:
            riga_spacchettata = spacchetta_movimenti_completo(riga)
            lista_movimenti.append(riga_spacchettata)
    return lista_movimenti

@app.get("/movimenti/{id_utente}")
def movimenti_utente(id_utente: int, tipo_movimenti: str = None, data: str = None, id_responsabile: int = Depends(controlla_ruolo_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    controlla_utente(conn, id_utente)
    if tipo_movimenti is not None and tipo_movimenti not in ["carico", "prelievo"]:
        raise HTTPException(status_code = 400, detail = "Tipo di movimento non trovato")
    cursore = conn.execute("""SELECT movimenti.id, utenti.id, utenti.nome, movimenti.quantita, movimenti.tipo, articoli.nome, movimenti.giacenza_dopo_movimento, movimenti.data FROM movimenti
                            LEFT JOIN utenti on movimenti.id_utente = utenti.id
                            LEFT JOIN articoli on movimenti.id_articolo = articoli.id
                            WHERE utenti.id = ? ORDER by movimenti.data""", (id_utente, ))
    utente = cursore.fetchall()
    lista_movimenti_utente = []
    totale_per_utente_carico = 0
    totale_per_utente_prelievo = 0
    for riga in utente:
        passa_data = data is None or data == riga[7][:10]
        passa_tipo = tipo_movimenti is None or tipo_movimenti == riga[4]
        if passa_tipo and passa_data:
            if riga[4] =="carico":
                totale_per_utente_carico+=riga[3]
            else:
                totale_per_utente_prelievo+=riga[3]
            riga_utente = spacchetta_movimenti_completo(riga)
            lista_movimenti_utente.append(riga_utente)
    if tipo_movimenti is None:
        return {"movimenti": lista_movimenti_utente, "totale_carico": totale_per_utente_carico, "totale_prelievo": totale_per_utente_prelievo}
    return {"movimenti": lista_movimenti_utente, "totale" : totale_per_utente_prelievo+totale_per_utente_carico}
    
@app.get("/utenti")
def mostra_utenti(id_responsabile: int = Depends(controlla_ruolo_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    cursore_utenti = conn.execute("SELECT * FROM utenti")
    lista_utenti = cursore_utenti.fetchall()
    lista_finale = []
    for riga in lista_utenti:
        utente = {"id": riga[0], "nome": riga[1]}
        lista_finale.append(utente)
    return lista_finale

@app.get("/utenti/{id_utente}")
def cerca_utente(id_utente: int, id_responsabile: int = Depends(controlla_ruolo_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    riga_utente = controlla_utente(conn, id_utente)
    return {"id": riga_utente[0], "nome": riga_utente[1]}

@app.delete("/utenti/{id_utente}")
def rimuovi_utente(id_utente: int, id_responsabile: int = Depends(controlla_ruolo_responsabile), conn: sqlite3.Connection = Depends(apri_db)):
    riga_utente = controlla_utente(conn, id_utente)
    controlla_movimento_utente(conn, id_utente)
    conn.execute("DELETE FROM sessioni WHERE id_utente = ?", (id_utente, ))
    conn.execute("DELETE FROM utenti WHERE id = ?", (id_utente, ))
    conn.commit()
    return {"id": riga_utente[0], "nome": riga_utente[1]}
