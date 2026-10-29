from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from database import apri_connessione, crea_tabella, spacchetta_riga_articolo, controlla_articolo, controlla_utente, crea_movimento, spacchetta_movimenti_completo, controlla_movimento_prodotto, controlla_movimento_utente, controlla_token, controlla_ruolo_addetto_responsabile, controlla_ruolo_responsabile
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

crea_tabella()

@app.post("/utenti")
def nuovo_utente(nuovo: Utente, authorization: str | None = Header(default = None)):
    username = nuovo.username.lower()
    ruolo = nuovo.ruolo.lower()
    nome = nuovo.nome.lower()
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente)
    if ruolo not in ["addetto", "responsabile"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Inserire addetto o responsabile")
    cursore_username = conn.execute("SELECT * FROM utenti WHERE username = ?", (username, ))
    controllo_username = cursore_username.fetchone()
    if controllo_username is not None:
        conn.close()
        raise HTTPException(status_code=409, detail="Username gia in uso")
    hash_utente = password_hash.hash(nuovo.password)
    cursore = conn.execute("INSERT INTO utenti (nome, username, ruolo, hash) VALUES (?, ?, ?, ?)", (nome, username, ruolo, hash_utente))
    riga_nuovo_utente = cursore.lastrowid
    conn.commit()
    conn.close()
    return {"id": riga_nuovo_utente, "nome": nome, "username": username, "ruolo": ruolo}

@app.post("/login")
def login_utente(utente: LoginUtente):
    username = utente.username.lower()
    conn = apri_connessione()
    cursore = conn.execute("SELECT hash, utenti.id FROM utenti WHERE username = ?", (username, ))
    riga = cursore.fetchone()
    if riga is None or riga[0] is None:
        conn.close()
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    hash_utente = riga[0]
    id_utente = riga[1]
    verifica = password_hash.verify(utente.password, hash_utente)
    if verifica:
        token = secrets.token_urlsafe(32)
        scadenza = datetime.now().replace(microsecond=0) + timedelta(hours=8)
        conn.execute("INSERT INTO sessioni (id_utente, token, scadenza) VALUES (?, ?, ?)", (id_utente, token, str(scadenza)))
        conn.commit()
        conn.close()
        return {"token": token}
    else:
        conn.close()
        raise HTTPException(status_code=401, detail="Credenziali non valide")

@app.post("/catalogo")
def aggiungi_articolo(articolo: Articolo, authorization: str | None = Header(default = None)):
    data = str(datetime.now().replace(microsecond = 0))
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_addetto_responsabile(conn, id_utente)
    cursore = conn.execute("""
        INSERT INTO articoli (nome, prezzo, categoria, quantita, data_inserimento, data_ultimo_movimento)
        VALUES (?, ?, ?, ?, ?, ? )""", 
        (articolo.nome, articolo.prezzo, articolo.categoria, articolo.quantita, data, data))
    ultimo_id = cursore.lastrowid
    conn.commit()
    conn.close()
    return {"id": ultimo_id, "Prodotto": articolo}

@app.get("/catalogo")
def trova_prodotti(prezzo_inferiore_a: float = None, categoria: str = None, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_addetto_responsabile(conn, id_utente)
    cursore = conn.execute("SELECT * FROM articoli")
    righe = cursore.fetchall()
    conn.close()
    lista_prodotti = []
    for riga in righe:
        dizionario_prodotti = spacchetta_riga_articolo(riga)
        lista_prodotti.append(dizionario_prodotti)
    finale = []
    for prodotto in lista_prodotti:
        passa_categoria  =  categoria is None or categoria.lower() == prodotto["categoria"].lower()
        passa_prezzo = prezzo_inferiore_a is None or prezzo_inferiore_a>=prodotto["prezzo"]
        if passa_categoria and passa_prezzo:
            finale.append(prodotto)
    return finale

@app.get("/catalogo/{id_prodotto}")
def cerca_id(id_prodotto: int, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_addetto_responsabile(conn, id_utente)
    riga = controlla_articolo(conn, id_prodotto,)
    conn.close()
    prodotto = spacchetta_riga_articolo(riga)
    return prodotto
  
@app.delete("/catalogo/{id_prodotto}")
def rimuovi_prodotto(id_prodotto: int, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente)
    riga = controlla_articolo(conn, id_prodotto)
    controlla_movimento_prodotto(conn, id_prodotto)
    prodotto_eliminato = spacchetta_riga_articolo(riga)
    conn.execute("DELETE FROM articoli WHERE id = ?", (id_prodotto, ))
    conn.commit()
    conn.close()    
    return prodotto_eliminato

@app.patch("/catalogo/{id_prodotto}")
def modifica_articolo(articolo: ModificaArticolo, id_prodotto: int, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente)
    controlla_articolo(conn, id_prodotto,)
    conn.execute("UPDATE articoli SET nome = coalesce(?, nome), prezzo = coalesce(?, prezzo), categoria = coalesce(?, categoria) WHERE id = ?", (articolo.nome, articolo.prezzo, articolo.categoria, id_prodotto))
    cursore_aggiornato = conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato = cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale = spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/carico")
def carica_quantita_articolo(richiesta: CaricoPrelievo, id_prodotto: int, authorization: str | None = Header(default = None)):
    data = str(datetime.now().replace(microsecond = 0))
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_addetto_responsabile(conn, id_utente)
    controlla_articolo(conn, id_prodotto,)
    controlla_utente(conn, id_utente)
    conn.execute("""UPDATE articoli SET quantita = quantita + ?, data_ultimo_movimento = ? WHERE id = ?""", (richiesta.quantita, data, id_prodotto))
    cursore_aggiornato = conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato = cursore_aggiornato.fetchone()
    giacenza_aggiornata = prodotto_aggiornato[4]
    movimento = crea_movimento(conn, id_utente, id_prodotto, richiesta.quantita, "carico", giacenza_aggiornata)
    conn.commit()
    conn.close()
    prodotto_finale = spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale, movimento

@app.patch("/catalogo/{id_prodotto}/prelievo")
def preleva_merce(richiesta: CaricoPrelievo, id_prodotto: int, authorization: str | None = Header(default = None)):
    data = str(datetime.now().replace(microsecond = 0))
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_addetto_responsabile(conn, id_utente)
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
    conn.close()
    prodotto_finale = spacchetta_riga_articolo(prodotto_aggiornato)
    if richiesta.quantita>quantita_prodotto_attuale:
        calcolo_prelievo = richiesta.quantita-quantita_prodotto_attuale
        prodotto_finale["mancanti"] = calcolo_prelievo
        return prodotto_finale, movimento
    prodotto_finale["mancanti"] = 0
    return prodotto_finale, movimento

@app.get("/movimenti")
def movimenti_completo(data : str = None, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente)
    cursore = conn.execute("""SELECT movimenti.id, utenti.id, utenti.nome, movimenti.quantita, movimenti.tipo, articoli.nome, movimenti.giacenza_dopo_movimento, movimenti.data FROM movimenti
                            LEFT JOIN utenti on movimenti.id_utente = utenti.id
                            LEFT JOIN articoli on movimenti.id_articolo = articoli.id""")
    movimenti = cursore.fetchall()
    conn.close()
    lista_movimenti = []
    for riga in movimenti:
        if data is None or data == riga[7][:10]:
            riga_spacchettata = spacchetta_movimenti_completo(riga)
            lista_movimenti.append(riga_spacchettata)
    return lista_movimenti

@app.get("/movimenti/{id_utente}")
def movimenti_utente(id_utente: int, tipo_movimenti: str = None, data: str = None, authorization: str | None = Header(default= None)):
    if tipo_movimenti is not None and tipo_movimenti not in ["carico", "prelievo"]:
        raise HTTPException(status_code = 400, detail = "Tipo di movimento non trovato")
    conn = apri_connessione()
    id_utente_autorizzato = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente_autorizzato)
    controlla_utente(conn, id_utente)
    cursore = conn.execute("""SELECT movimenti.id, utenti.id, utenti.nome, movimenti.quantita, movimenti.tipo, articoli.nome, movimenti.giacenza_dopo_movimento, movimenti.data FROM movimenti
                            LEFT JOIN utenti on movimenti.id_utente = utenti.id
                            LEFT JOIN articoli on movimenti.id_articolo = articoli.id
                            WHERE utenti.id = ? ORDER by movimenti.data""", (id_utente, ))
    utente = cursore.fetchall()
    conn.close()
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
def mostra_utenti(authorization: str | None = Header(default= None)):
    conn = apri_connessione()
    id_utente = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente)
    cursore_utenti = conn.execute("SELECT * FROM utenti")
    lista_utenti = cursore_utenti.fetchall()
    conn.close()
    lista_finale = []
    for riga in lista_utenti:
        utente = {"id": riga[0], "nome": riga[1]}
        lista_finale.append(utente)
    return lista_finale

@app.get("/utenti/{id_utente}")
def cerca_utente(id_utente: int, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente_autorizzato = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente_autorizzato)
    riga_utente = controlla_utente(conn, id_utente)
    conn.close()
    return {"id": riga_utente[0], "nome": riga_utente[1]}

@app.delete("/utenti/{id_utente}")
def rimuovi_utente(id_utente: int, authorization: str | None = Header(default = None)):
    conn = apri_connessione()
    id_utente_autorizzato = controlla_token(conn, authorization)
    controlla_ruolo_responsabile(conn, id_utente_autorizzato)
    riga_utente = controlla_utente(conn, id_utente)
    controlla_movimento_utente(conn, id_utente)
    conn.execute("DELETE FROM sessioni WHERE id_utente = ?", (id_utente, ))
    conn.execute("DELETE FROM utenti WHERE id = ?", (id_utente, ))
    conn.commit()
    conn.close()
    return {"id": riga_utente[0], "nome": riga_utente[1]}
