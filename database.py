import sqlite3
import os
from fastapi import HTTPException

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB = os.path.join(CARTELLA, "script_gestionale_magazzino.db")

def apri_connessione():
    conn=sqlite3.connect(PERCORSO_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def crea_tabella():
    conn=apri_connessione()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articoli (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            prezzo REAL,
            categoria TEXT,
            quantita INTEGER,
            data_inserimento TEXT,
            data_ultimo_movimento TEXT )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY, 
            nome TEXT)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movimenti (
            id INTEGER PRIMARY KEY, 
            id_utente INTEGER,
            id_articolo INTEGER,
            quantita INTEGER,
            tipo TEXT, 
            data TEXT, 
            FOREIGN KEY (id_utente) REFERENCES utenti(id), 
            FOREIGN KEY (id_articolo) REFERENCES articoli(id))""")
    conn.commit()
    conn.close()

def spacchetta_riga_articolo(riga):
    return {"id": riga[0], "nome": riga[1], "prezzo": riga[2], "categoria": riga[3], "quantita": riga[4], "data_inserimento": riga[5], "data_ultimo_movimento": riga[6]}

def controlla_articolo(id_prodotto, conn):
    cursore=conn.execute("SELECT * FROM articoli WHERE id=?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return riga_selezionata