from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from database import apri_connessione, crea_tabella, spacchetta_riga_articolo, controlla_articolo, controlla_utente, crea_movimento
app= FastAPI()

class Articolo(BaseModel):
    nome: str
    prezzo: float
    categoria: str
    quantita: int

class ModificaArticolo(BaseModel):
    nome: str | None=None
    prezzo: float | None=None
    categoria: str | None=None

class CaricoPrelievo(BaseModel):
    quantita: int
    id_utente: int

class Utente(BaseModel):
    nome: str

crea_tabella()

@app.post("/utenti")
def nuovo_utente(nuovo: Utente):
    conn=apri_connessione()
    cursore=conn.execute("INSERT INTO utenti (nome) VALUES (?)", (nuovo.nome, ))
    riga_nuovo_utente=cursore.lastrowid
    conn.commit()
    conn.close()
    return {"id": riga_nuovo_utente, "nome": nuovo.nome}

@app.post("/catalogo")
def aggiungi_articolo(articolo: Articolo):
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    cursore=conn.execute("""
        INSERT INTO articoli (nome, prezzo, categoria, quantita, data_inserimento, data_ultimo_movimento)
        VALUES (?, ?, ?, ?, ?, ? )""", 
        (articolo.nome, articolo.prezzo, articolo.categoria, articolo.quantita, data, data))
    ultimo_id=cursore.lastrowid
    conn.commit()
    conn.close()
    return {"id": ultimo_id, "Prodotto": articolo}

@app.get("/catalogo")
def trova_prodotti(prezzo_inferiore_a: float=None, categoria: str=None):
    conn=apri_connessione()
    cursore=conn.execute("SELECT * FROM articoli")
    righe=cursore.fetchall()
    conn.close()
    lista_prodotti=[]
    for riga in righe:
        dizionario_prodotti=spacchetta_riga_articolo(riga)
        lista_prodotti.append(dizionario_prodotti)
    finale=[]
    for prodotto in lista_prodotti:
        passa_categoria = categoria is None or categoria.lower() == prodotto["categoria"].lower()
        passa_prezzo = prezzo_inferiore_a is None or prezzo_inferiore_a>=prodotto["prezzo"]
        if passa_categoria and passa_prezzo:
            finale.append(prodotto)
    return finale

@app.get("/catalogo/{id_prodotto}")
def cerca_id(id_prodotto: int):
    conn=apri_connessione()
    riga=controlla_articolo(conn, id_prodotto,)
    conn.close()
    prodotto=spacchetta_riga_articolo(riga)
    return prodotto
  
@app.delete("/catalogo/{id_prodotto}")
def rimuovi_prodotto(id_prodotto: int):
    conn=apri_connessione()
    riga=controlla_articolo(conn, id_prodotto,)
    prodotto_eliminato=spacchetta_riga_articolo(riga)
    conn.execute("DELETE FROM articoli WHERE id=?", (id_prodotto, ))
    conn.commit()
    conn.close()    
    return prodotto_eliminato

@app.patch("/catalogo/{id_prodotto}")
def modifica_articolo(articolo: ModificaArticolo, id_prodotto: int):
    conn=apri_connessione()
    riga=controlla_articolo(conn, id_prodotto,)
    conn.execute("UPDATE articoli SET nome = coalesce(?, nome), prezzo = coalesce(?, prezzo), categoria = coalesce(?, categoria) WHERE id = ?", (articolo.nome, articolo.prezzo, articolo.categoria, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/carico")
def carica_quantita_articolo(utente: CaricoPrelievo, id_prodotto: int):
    if utente.quantita<=0:
        raise HTTPException(status_code=400, detail="La quantità deve essere magigore di zero")
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    riga=controlla_articolo(conn, id_prodotto,)
    id_utente=controlla_utente(conn, utente.id_utente)
    movimento=crea_movimento(conn, utente.id_utente, id_prodotto, utente.quantita, "carico")
    conn.execute("""UPDATE articoli SET quantita = quantita + ?, data_ultimo_movimento = ? WHERE id = ?""", (utente.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale, movimento

@app.patch("/catalogo/{id_prodotto}/prelievo")
def preleva_merce(utente: CaricoPrelievo, id_prodotto: int):
    if utente.quantita<=0:
        raise HTTPException(status_code=400, detail="Quantita da prelevare non valida")
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    riga=controlla_articolo(conn, id_prodotto,)
    id_utente=controlla_utente(conn, utente.id_utente)
    quantita_prodotto_attuale=riga[4]
    if utente.quantita<quantita_prodotto_attuale:
        quantita_prelevata=utente.quantita
    else:
        quantita_prelevata=quantita_prodotto_attuale
    movimento=crea_movimento(conn, utente.id_utente, id_prodotto, quantita_prelevata, "prelievo")
    conn.execute("""UPDATE articoli SET
        quantita = CASE WHEN ? <= quantita THEN quantita - ? WHEN ? > quantita THEN 0 END,
        data_ultimo_movimento = ?  WHERE id = ?""", (utente.quantita, utente.quantita, utente.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    if utente.quantita>quantita_prodotto_attuale:
        calcolo_prelievo=utente.quantita-quantita_prodotto_attuale
        prodotto_finale["mancanti"]=calcolo_prelievo
        return prodotto_finale, movimento
    prodotto_finale["mancanti"]=0
    return prodotto_finale, movimento