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
    data=datetime.now().replace(microsecond=0)
    conn=sqlite3.connect(PERCORSO_DB)
    conn.execute("""
        INSERT INTO GESTIONALE_MAGAZZINO (nome, prezzo, categoria, quantita, data_inserimento)
        VALUES (?, ?, ?, ?, ? )""", 
        (articolo.nome, articolo.prezzo, articolo.categoria, articolo.quantita, data))
    cursore=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO")
    ultimo_id=cursore.lastrowid
    conn.commit()
    conn.close()
    return {"id": ultimo_id, "Prodotto": articolo}