from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from database import apri_connessione, crea_tabella, spacchetta_riga_articolo, controlla_articolo
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

crea_tabella()

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
    riga=controlla_articolo(id_prodotto, conn)
    conn.close()
    prodotto=spacchetta_riga_articolo(riga)
    return prodotto
  
@app.delete("/catalogo/{id_prodotto}")
def rimuovi_prodotto(id_prodotto: int):
    conn=apri_connessione()
    riga=controlla_articolo(id_prodotto, conn)
    prodotto_eliminato=spacchetta_riga_articolo(riga)
    conn.execute("DELETE FROM articoli WHERE id=?", (id_prodotto, ))
    conn.commit()
    conn.close()
    return prodotto_eliminato

@app.patch("/catalogo/{id_prodotto}")
def modifica_articolo(articolo: ModificaArticolo, id_prodotto: int):
    conn=apri_connessione()
    riga=controlla_articolo(id_prodotto, conn)
    conn.execute("UPDATE articoli SET nome = coalesce(?, nome), prezzo = coalesce(?, prezzo), categoria = coalesce(?, categoria) WHERE id = ?", (articolo.nome, articolo.prezzo, articolo.categoria, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/carico")
def carica_quantita_articolo(articolo: CaricoPrelievo, id_prodotto: int):
    if articolo.quantita<=0:
        raise HTTPException(status_code=400, detail="La quantità deve essere magigore di zero")
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    riga=controlla_articolo(id_prodotto, conn)
    conn.execute("""UPDATE articoli SET quantita = quantita + ?, data_ultimo_movimento = ? WHERE id = ?""", (articolo.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    return prodotto_finale

@app.patch("/catalogo/{id_prodotto}/prelievo")
def preleva_merce(articolo: CaricoPrelievo, id_prodotto: int):
    if articolo.quantita<=0:
        raise HTTPException(status_code=400, detail="Quantita da prelevare non valida")
    data=str(datetime.now().replace(microsecond=0))
    conn=apri_connessione()
    riga=controlla_articolo(id_prodotto, conn)
    quantita_prodotto_attuale=riga[4]
    conn.execute("""UPDATE articoli SET
        quantita = CASE WHEN ? <= quantita THEN quantita - ? WHEN ? > quantita THEN 0 END,
        data_ultimo_movimento = ?  WHERE id = ?""", (articolo.quantita, articolo.quantita, articolo.quantita, data, id_prodotto))
    cursore_aggiornato=conn.execute("SELECT * FROM articoli WHERE id = ?", (id_prodotto, ))
    prodotto_aggiornato=cursore_aggiornato.fetchone()
    conn.commit()
    conn.close()
    prodotto_finale=spacchetta_riga_articolo(prodotto_aggiornato)
    if articolo.quantita>quantita_prodotto_attuale:
        calcolo_prelievo=articolo.quantita-quantita_prodotto_attuale
        prodotto_finale["mancanti"]=calcolo_prelievo
        return prodotto_finale
    prodotto_finale["mancanti"]=0
    return prodotto_finale