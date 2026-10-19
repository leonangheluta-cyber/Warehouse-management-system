import sqlite3
import os
from fastapi import HTTPException
from datetime import datetime

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
            giacenza_dopo_movimento INTEGER, 
            FOREIGN KEY (id_utente) REFERENCES utenti(id), 
            FOREIGN KEY (id_articolo) REFERENCES articoli(id))""")
    conn.commit()
    conn.close()

def spacchetta_riga_articolo(riga):
    return {"id": riga[0], "nome": riga[1], "prezzo": riga[2], "categoria": riga[3], "quantita": riga[4], "data_inserimento": riga[5], "data_ultimo_movimento": riga[6]}

def spacchetta_riga_movimento(riga):
    return {"id": riga[0], "id_utente": riga[1], "id_articolo": riga[2], "quantita": riga[3], "tipo": riga[4], "data": riga[5], "giacenza_post_movimento": riga[6]}

def spacchetta_movimenti_completo(riga):
    return {"id": riga[0], "id_utente": riga[1], "nome_utente": riga[2], "quantita": riga[3], "movimento": riga[4], "articolo": riga[5], "qta_post_movimento": riga[6], "data_movimento": riga[7]}

def controlla_articolo(conn, id_prodotto):
    cursore=conn.execute("SELECT * FROM articoli WHERE id=?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return riga_selezionata

def controlla_utente(conn, id_utente):
    cursore=conn.execute("SELECT * FROM utenti WHERE id = ?", (id_utente, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return riga_selezionata

def crea_movimento(conn, id_utente, id_articolo, quantita, tipo, giacenza_post_movimento):
    data=str(datetime.now().replace(microsecond=0))
    cursore=conn.execute("""INSERT INTO movimenti (id_utente, id_articolo, quantita, tipo, data, giacenza_dopo_movimento) VALUES (?, ?, ?, ?, ?, ?)""", (id_utente, id_articolo, quantita, tipo, data, giacenza_post_movimento))
    id_riga=cursore.lastrowid
    cursore_riga=conn.execute("SELECT * FROM movimenti WHERE id = ?", (id_riga, ))
    riga_movimento=cursore_riga.fetchone()
    riga_finale=spacchetta_riga_movimento(riga_movimento)
    return riga_finale
