from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import os

CARTELLA=os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB=os.path.join(CARTELLA, "script_gestionale_magazzino.db")
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

def crea_tabella():
    conn=sqlite3.connect(PERCORSO_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS GESTIONALE_MAGAZZINO (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            prezzo REAL,
            categoria TEXT,
            quantita INT,
            data_inserimento TEXT,
            data_ultimo_movimento TEXT )""")
    conn.commit()
    conn.close()

crea_tabella()

@app.post("/catalogo")
def aggiungi_articolo(articolo: Articolo):
    data=str(datetime.now().replace(microsecond=0))
    conn=sqlite3.connect(PERCORSO_DB)
    cursore=conn.execute("""
        INSERT INTO GESTIONALE_MAGAZZINO (nome, prezzo, categoria, quantita, data_inserimento, data_ultimo_movimento)
        VALUES (?, ?, ?, ?, ?, ? )""", 
        (articolo.nome, articolo.prezzo, articolo.categoria, articolo.quantita, data, data))
    ultimo_id=cursore.lastrowid
    conn.commit()
    conn.close()
    return {"id": ultimo_id, "Prodotto": articolo}

@app.get("/catalogo")
def trova_prodotti(prezzo_inferiore_a: float=None, categoria: str=None):
    conn=sqlite3.connect(PERCORSO_DB)
    cursore=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO")
    righe=cursore.fetchall()
    conn.close()
    prodotti={}
    for riga in righe:
        prodotti[riga[0]]={"nome": riga[1], "prezzo": riga[2], "categoria": riga[3], "quantita": riga[4], "data_inserimento": riga[5], "data_ultimo_movimento": riga[6]}
    nuovo={}
    for id, prodotto in prodotti.items():
        passa_categoria = categoria is None or categoria.lower() == prodotto["categoria"].lower()
        passa_prezzo = prezzo_inferiore_a is None or prezzo_inferiore_a>=prodotto["prezzo"]
        if passa_categoria and passa_prezzo:
            nuovo[id]=prodotto
    return nuovo

@app.get("/catalogo/{id_prodotto}")
def cerca_id(id_prodotto: int):
    conn=sqlite3.connect(PERCORSO_DB)
    cursore=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id=?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    conn.close()
    nuovo={}
    if riga_selezionata is not None:
        nuovo[riga_selezionata[0]]={"nome": riga_selezionata[1], "prezzo": riga_selezionata[2], "categoria": riga_selezionata[3], "quantita": riga_selezionata[4], "data_inserimento": riga_selezionata[5], "data_ultimo_movimento": riga_selezionata[6]}
        return nuovo
    else:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

@app.delete("/catalogo/{id_prodotto}")
def rimuovi_prodotto(id_prodotto: int):
    conn=sqlite3.connect(PERCORSO_DB)
    cursore=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id=?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata is not None:
        prodotto_eliminato={}
        prodotto_eliminato[riga_selezionata[0]]={"nome": riga_selezionata[1], "prezzo": riga_selezionata[2], "categoria": riga_selezionata[3], "quantita": riga_selezionata[4], "data_inserimento": riga_selezionata[5], "data_ultimo_movimento": riga_selezionata[6]}
        conn.execute("DELETE FROM GESTIONALE_MAGAZZINO WHERE id=?", (id_prodotto, ))
        conn.commit()
        conn.close()
        return prodotto_eliminato
    else:
        conn.close()
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

@app.patch("/catalogo/{id_prodotto}")
def modifica_articolo(articolo: ModificaArticolo, id_prodotto: int):
    conn=sqlite3.connect(PERCORSO_DB)
    cursore_id=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id = ?", (id_prodotto, ))
    prodotto_scelto=cursore_id.fetchone()
    if prodotto_scelto is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    conn.execute("UPDATE GESTIONALE_MAGAZZINO SET nome = coalesce(?, nome), prezzo = coalesce(?, prezzo), categoria = coalesce(?, categoria) WHERE id = ?", (articolo.nome, articolo.prezzo, articolo.categoria, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale={"id":prodotto_aggiornato[0], "nome": prodotto_aggiornato[1], "prezzo": prodotto_aggiornato[2], "categoria": prodotto_aggiornato[3], "quantita": prodotto_aggiornato[4], "data_inserimento": prodotto_aggiornato[5], "data_ultimo_movimento": prodotto_aggiornato[6]}
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/carico")
def carica_quantita_articolo(articolo: CaricoPrelievo, id_prodotto: int):
    if articolo.quantita<=0:
        raise HTTPException(status_code=400, detail="La quantità deve essere magigore di zero")
    data=str(datetime.now().replace(microsecond=0))
    conn=sqlite3.connect(PERCORSO_DB)
    cursore_id=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id = ?", (id_prodotto, ))
    prodotto_scelto=cursore_id.fetchone()
    if prodotto_scelto is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    conn.execute("""UPDATE GESTIONALE_MAGAZZINO SET quantita = quantita + ?, data_ultimo_movimento = ? WHERE id = ?""", (articolo.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale={"id":prodotto_aggiornato[0], "nome": prodotto_aggiornato[1], "prezzo": prodotto_aggiornato[2], "categoria": prodotto_aggiornato[3], "quantita": prodotto_aggiornato[4], "data_inserimento": prodotto_aggiornato[5], "data_ultimo_movimento": prodotto_aggiornato[6]}
    return prodotto_finale