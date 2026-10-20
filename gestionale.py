from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from database import apri_connessione, crea_tabella, spacchetta_riga_articolo, controlla_articolo, controlla_utente, crea_movimento, spacchetta_movimenti_completo
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
    if articolo.quantita<=0:
        raise HTTPException(status_code=400, detail="Inserisci una quantita valida")
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
    controlla_articolo(conn, id_prodotto,)
    conn.execute("UPDATE articoli SET nome = coalesce(?, nome), prezzo = coalesce(?, prezzo), categoria = coalesce(?, categoria) WHERE id = ?", (articolo.nome, articolo.prezzo, articolo.categoria, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/carico")
def carica_quantita_articolo(richiesta: CaricoPrelievo, id_prodotto: int):
    if richiesta.quantita<=0:
        raise HTTPException(status_code=400, detail="La quantità deve essere maggiore di zero")
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    controlla_articolo(conn, id_prodotto,)
    controlla_utente(conn, richiesta.id_utente)
    conn.execute("""UPDATE articoli SET quantita = quantita + ?, data_ultimo_movimento = ? WHERE id = ?""", (richiesta.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    giacenza_aggiornata=prodotto_aggiornato[4]
    movimento=crea_movimento(conn, richiesta.id_utente, id_prodotto, richiesta.quantita, "carico", giacenza_aggiornata)
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale, movimento

@app.patch("/catalogo/{id_prodotto}/prelievo")
def preleva_merce(richiesta: CaricoPrelievo, id_prodotto: int):
    if richiesta.quantita<=0:
        raise HTTPException(status_code=400, detail="Quantita da prelevare non valida")
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    riga=controlla_articolo(conn, id_prodotto,)
    controlla_utente(conn, richiesta.id_utente)
    quantita_prodotto_attuale=riga[4]
    if richiesta.quantita<quantita_prodotto_attuale:
        quantita_prelevata=richiesta.quantita
    else:
        quantita_prelevata=quantita_prodotto_attuale
    conn.execute("""UPDATE articoli SET
        quantita = CASE WHEN ? <= quantita THEN quantita - ? WHEN ? > quantita THEN 0 END,
        data_ultimo_movimento = ?  WHERE id = ?""", (richiesta.quantita, richiesta.quantita, richiesta.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    giacenza_finale=prodotto_aggiornato[4]
    movimento=crea_movimento(conn, richiesta.id_utente, id_prodotto, quantita_prelevata, "prelievo", giacenza_finale)
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    if richiesta.quantita>quantita_prodotto_attuale:
        calcolo_prelievo=richiesta.quantita-quantita_prodotto_attuale
        prodotto_finale["mancanti"]=calcolo_prelievo
        return prodotto_finale, movimento
    prodotto_finale["mancanti"]=0
    return prodotto_finale, movimento

@app.get("/movimenti")
def controlla_movimenti():
    conn=apri_connessione()
    cursore=conn.execute("""SELECT movimenti.id, utenti.id, utenti.nome, movimenti.quantita, movimenti.tipo, articoli.nome, movimenti.giacenza_dopo_movimento, movimenti.data FROM movimenti
                            LEFT JOIN utenti on movimenti.id_utente=utenti.id
                            LEFT JOIN articoli on movimenti.id_articolo=articoli.id""")
    movimenti=cursore.fetchall()
    conn.close()
    lista_movimenti=[]
    for riga in movimenti:
        riga_spacchettata=spacchetta_movimenti_completo(riga)
        lista_movimenti.append(riga_spacchettata)
    return lista_movimenti