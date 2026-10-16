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

def riga_in_dizionario(riga):
    return {"id": riga[0], "nome": riga[1], "prezzo": riga[2], "categoria": riga[3], "quantita": riga[4], "data_inserimento": riga[5], "data_ultimo_movimento": riga[6]}
    
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
    lista_prodotti=[]
    for riga in righe:
        dizionario_prodotti=riga_in_dizionario(riga)
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
    conn=sqlite3.connect(PERCORSO_DB)
    cursore=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id=?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    conn.close()
    if riga_selezionata is not None:
        prodotto=riga_in_dizionario(riga_selezionata)
        return prodotto
    else:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

@app.delete("/catalogo/{id_prodotto}")
def rimuovi_prodotto(id_prodotto: int):
    conn=sqlite3.connect(PERCORSO_DB)
    cursore=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id=?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    prodotto_eliminato=riga_in_dizionario(riga_selezionata)
    conn.execute("DELETE FROM GESTIONALE_MAGAZZINO WHERE id=?", (id_prodotto, ))
    conn.commit()
    conn.close()
    return prodotto_eliminato

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
    prodotto_finale=riga_in_dizionario(prodotto_aggiornato)
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
    prodotto_finale=riga_in_dizionario(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/prelievo")
def preleva_merce(articolo: CaricoPrelievo, id_prodotto: int):
    if articolo.quantita<=0:
        raise HTTPException(status_code=400, detail="Quantita da prelevare non valida")
    data=str(datetime.now().replace(microsecond=0))
    conn=sqlite3.connect(PERCORSO_DB)
    cursore_id=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id = ?", (id_prodotto, ))
    prodotto_scelto=cursore_id.fetchone()
    if prodotto_scelto is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    quantita_prodotto_attuale=prodotto_scelto[4]
    conn.execute("""UPDATE GESTIONALE_MAGAZZINO SET
        quantita = CASE WHEN ? <= quantita THEN quantita - ? WHEN ? > quantita THEN 0 END,
        data_ultimo_movimento = ?  WHERE id = ?""", (articolo.quantita, articolo.quantita, articolo.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM GESTIONALE_MAGAZZINO WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=riga_in_dizionario(prodotto_aggiornato)
    if articolo.quantita>quantita_prodotto_attuale:
        calcolo_prelievo=articolo.quantita-quantita_prodotto_attuale
        prodotto_finale["mancanti"]=calcolo_prelievo
        return prodotto_finale
    prodotto_finale["mancanti"]=0
    return prodotto_finale
    