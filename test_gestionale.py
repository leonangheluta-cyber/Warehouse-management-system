from fastapi.testclient import TestClient
import database
import os
from datetime import datetime
import pytest

CARTELLA=os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB_PROVA=os.path.join(CARTELLA, "gestionale_test.db")
database.PERCORSO_DB=PERCORSO_DB_PROVA

from gestionale import app # --> IMPORT DOPO IL CAMBIO DI PERCORSO, gestionale.py CREA LòA TABELLA APPENA VIENE IMPORTATA
client=TestClient(app)

data=str(datetime.now().replace(microsecond=0))

def aggiungi_dati_db_prova():
    conn=database.apri_connessione()
    conn.executemany("""INSERT INTO articoli (nome, prezzo, categoria, quantita, data_inserimento) VALUES (?, ?, ?, ?, ?)""",
                        (("Mouse gaming", 25, "mouse", 15, data), ("Monitor LG 2k", 250, "monitor", 24, data), ("Tastiera meccanica", 25, "tastiere", 15, data)))
    conn.executemany("INSERT INTO utenti (nome) VALUES (?)", (("Leon", ), ("Mario", )))
    conn.executemany("INSERT INTO movimenti (id_utente, id_articolo, quantita, tipo, data, giacenza_dopo_movimento) VALUES (?, ?, ?, ?, ?, ?)",
                    ((1, 1, 10, "carico", data, 15), (1, 2, 10, "prelievo", data, 24)))
    conn.commit()
    conn.close()

@pytest.fixture(autouse=True)
def crea_db_prova():
    if os.path.exists(PERCORSO_DB_PROVA):
        os.remove(PERCORSO_DB_PROVA)
    database.crea_tabella()
    aggiungi_dati_db_prova()
    yield
    os.remove(PERCORSO_DB_PROVA)

PRODOTTO_VALIDO={"nome": "Tappetino mouse", "prezzo": 15, "categoria": "mouse", "quantita": 25}

def test_prova_funzione_fixture_aggiungi_prodotto():
    risposta = client.post("/catalogo", json=PRODOTTO_VALIDO)    
    assert risposta.status_code == 200
    id_nuovo_prodotto = risposta.json()["id"]
    assert risposta.json()["Prodotto"]["nome"] == PRODOTTO_VALIDO["nome"]
    richiesta_nuovo = client.get(f"/catalogo/{id_nuovo_prodotto}")
    assert richiesta_nuovo.status_code == 200
    assert richiesta_nuovo.json()["id"] == id_nuovo_prodotto
### FUNZIONE DI PROVA PER IL FIXTURE
def test_get_prodotto_cancellato_funzione_fixture():
    risposta = client.get("/catalogo/4")
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_utente_corto():
    risposta = client.post("/utenti", json = {"nome": "a"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "nome"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_aggiungi_articolo_nome_corto():
    dati = PRODOTTO_VALIDO.copy()
    dati["nome"] = "a"
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "nome"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_aggiungi_articolo_prezzo_zero():
    dati = PRODOTTO_VALIDO.copy()
    dati["prezzo"] = 0
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "prezzo"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_aggiungi_articolo_categoria_corta():
    dati = PRODOTTO_VALIDO.copy()
    dati["categoria"] = "a"
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "categoria"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_aggiungi_articolo_quantita_zero():
    dati = PRODOTTO_VALIDO.copy()
    dati["quantita"] = 0
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "quantita"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_trova_prodotto_id_inesistente():
    risposta = client.get("/catalogo/9999")
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_rimuovi_prodotto_id_inesistente():
    risposta = client.delete("/catalogo/99999")
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_modifica_articolo_id_inesistente():
    risposta = client.patch("/catalogo/99999", json={})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_modifica_articolo_nome_corto():
    risposta = client.patch("/catalogo/1", json={"nome" : "a"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "nome"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_modifica_articolo_prezzo_zero():
    risposta = client.patch("/catalogo/1", json={"prezzo" : 0})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "prezzo"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_modifica_articolo_categoria_corto():
    risposta = client.patch("/catalogo/1", json={"categoria" : "a"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "categoria"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_trova_prodotti_categoria():
    risposta = client.get("/catalogo?categoria=mouse")
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["categoria"] == "mouse"

def test_trova_prodotti_filtro_prezzo():
    risposta = client.get("/catalogo?prezzo_inferiore_a=50")
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["prezzo"]<=50

def test_carico_quantita_valida():
    risposta = client.patch("/catalogo/1/carico", json={"quantita": 5, "id_utente": 1})
    assert risposta.status_code == 200
    assert risposta.json()[1]["quantita"] == 5

def test_carica_quantita_id_inesistente():
    risposta = client.patch("/catalogo/9999/carico" , json={"quantita": 5, "id_utente": 1})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_carica_quantita_zero():
    risposta = client.patch("/catalogo/1/carico" , json={"quantita": 0, "id_utente": 1})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "quantita"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_carica_quantita_id_utente_0():
    risposta = client.patch("/catalogo/1/carico" , json={"quantita": 5, "id_utente": 0})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "id_utente"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_carica_quantita_id_utente_inesistente():
    risposta = client.patch("/catalogo/1/carico" , json={"quantita": 5, "id_utente": 9999})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_preleva_quantita_id_inesistente():
    risposta = client.patch("/catalogo/9999/prelievo" , json={"quantita": 5, "id_utente": 1})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_preleva_quantita_zero():
    risposta = client.patch("/catalogo/1/prelievo" , json={"quantita": 0, "id_utente": 1})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "quantita"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_preleva_quantita_maggiore_di_stock():
    richiesta_giacenza = client.get("/catalogo/2")
    assert richiesta_giacenza.status_code == 200
    giacenza = richiesta_giacenza.json()["quantita"]
    risposta = client.patch("/catalogo/2/prelievo" , json={"quantita": 9999, "id_utente": 1})
    assert risposta.status_code == 200
    assert risposta.json()[0]["quantita"] == 0
    assert risposta.json()[0]["mancanti"] == 9999 - giacenza
    assert risposta.json()[1]["quantita"] == giacenza

def test_preleva_quantita_id_utente_0():
    risposta = client.patch("/catalogo/1/prelievo" , json={"quantita": 5, "id_utente": 0})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "id_utente"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_preleva_quantita_id_utente_inesistente():
    risposta = client.patch("/catalogo/1/prelievo" , json={"quantita": 5, "id_utente": 9999})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_movimenti_completo_filtro_data():
    solo_data=data.split(" ")[0]
    risposta = client.get(f"/movimenti?data={solo_data}")
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["data_movimento"].split(" ")[0] == solo_data

def test_movimenti_utente_inesistente():
    risposta = client.get("/movimenti/9999")
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_movimenti_filtro_carico():
    risposta = client.get("/movimenti/1?tipo_movimenti=carico")
    assert risposta.status_code == 200
    dati = risposta.json()["movimenti"]
    assert dati!= []
    for riga in dati:
        assert riga["movimento"] == "carico"

def test_mostra_utenti():
    risposta = client.get("/utenti")
    assert risposta.status_code == 200
    assert risposta.json() != []
    assert risposta.json()[0]["nome"] =="Leon"

def test_inserimenti_prodotto_valido():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 200
    id_nuovo_prodotto = risposta.json()["id"]
    rilettura = client.get(f"/catalogo/{id_nuovo_prodotto}")
    assert rilettura.status_code == 200
    assert rilettura.json()["id"] == id_nuovo_prodotto
    assert rilettura.json()["nome"] == PRODOTTO_VALIDO["nome"]

def test_rimuovi_utente_inesistente():
    risposta = client.delete("/utenti/9999")
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_trova_utente_id_inesistente():
    risposta = client.get("/utenti/9999")
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_rimuovi_utente_con_movimenti():
    risposta = client.delete("/utenti/1")
    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "Impossibile eliminare l'utente: presenta dei movimenti"
    controllo = client.get("/utenti/1")
    assert controllo.status_code == 200
    assert controllo.json()["id"] == 1

def test_rimuovi_utente_senza_movimenti():
    risposta = client.delete("/utenti/2")
    assert risposta.status_code == 200
    assert risposta.json()["id"] == 2
    controllo = client.get("/utenti/2")
    assert controllo.status_code == 404
    assert controllo.json()["detail"] == "Utente non trovato"

def test_rimuovi_articolo_con_movimenti():
    risposta = client.delete("/catalogo/1")
    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "Impossibile eliminare il prodotto: presenta dei movimenti"
    controllo = client.get("/catalogo/3")
    assert controllo.status_code == 200
    assert controllo.json()["id"] == 3

def test_rimuovi_articolo_senza_movimenti():
    risposta = client.delete("/catalogo/3")
    assert risposta.status_code == 200
    assert risposta.json()["id"] == 3
    controllo = client.get("/catalogo/3")
    assert controllo.status_code == 404
    assert controllo.json()["detail"] == "Articolo non trovato"