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
def trova_prodotti(prezzo_feriore_a: float=None, categoria: str=None):
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
        passa_prezzo = prezzo_feriore_a is None or prezzo_feriore_a>=prodotto["prezzo"]
        if passa_categoria and passa_prezzo:
            nuovo[id]=prodotto
    return nuovo