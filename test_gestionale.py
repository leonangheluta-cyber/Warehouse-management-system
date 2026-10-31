from fastapi.testclient import TestClient
import database
import os
from datetime import datetime
import pytest
from database import hash_password_gestionale, password_hash
hash_password_finta = password_hash.hash("cane12345")
CARTELLA=os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB_PROVA=os.path.join(CARTELLA, "gestionale_test.db")
database.PERCORSO_DB=PERCORSO_DB_PROVA

from gestionale import app, password_hash # --> IMPORT DOPO IL CAMBIO DI PERCORSO, gestionale.py CREA LòA TABELLA APPENA VIENE IMPORTATA
client=TestClient(app)
hash_password_addetto_1 = password_hash.hash("cane1234")
hash_password_addetto_2 = password_hash.hash("cane12345")
data=str(datetime.now().replace(microsecond=0))

PRODOTTO_VALIDO = {"nome": "Tappetino mouse", "prezzo": 15, "categoria": "mouse", "quantita": 25}
UTENTE_VALIDO = {"nome": "Mario", "username": "mario123", "ruolo": "addetto", "password": "cane12345"}

def aggiungi_dati_db_prova():
    conn=database.apri_connessione()
    conn.executemany("""INSERT INTO articoli (nome, prezzo, categoria, quantita, data_inserimento) VALUES (?, ?, ?, ?, ?)""",
                        (("Mouse gaming", 25, "mouse", 15, data), ("Monitor LG 2k", 250, "monitor", 24, data), ("Tastiera meccanica", 25, "tastiere", 15, data)))
    conn.executemany("INSERT INTO utenti (nome, username, ruolo, hash) VALUES (?, ?, ?, ?)", (("Franco", "franco", "addetto", hash_password_addetto_1), ("Marco", "marco", "addetto", hash_password_addetto_2)))
    conn.executemany("INSERT INTO movimenti (id_utente, id_articolo, quantita, tipo, data, giacenza_dopo_movimento) VALUES (?, ?, ?, ?, ?, ?)",
                    ((1, 1, 10, "carico", data, 15), (1, 2, 10, "prelievo", data, 24), (2, 1, 1, "carico", data, 24)))
    conn.executemany("INSERT INTO sessioni (id_utente, token, scadenza) VALUES (?, ?, ?)", ((1, "token_autorizzato", "2030-10-10 00:00:00"), (2, "TOKEN_SCADUTO", "2020-10-10 00:00:00"), (3, "token_non_autorizzato", "2030-10-10 00:00:00")))
    conn.commit()
    conn.close()

def registra_e_login():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    username = risposta.json()["username"]
    login = client.post("/login", json={"username": username, "password": UTENTE_VALIDO["password"]})
    token = login.json()["token"]
    return token

@pytest.fixture(autouse=True)
def crea_db_prova():
    if os.path.exists(PERCORSO_DB_PROVA):
        os.remove(PERCORSO_DB_PROVA)
    database.crea_tabella()
    aggiungi_dati_db_prova()
    yield
    os.remove(PERCORSO_DB_PROVA)

def test_ruolo_sbagliato():
    dati = UTENTE_VALIDO.copy()
    dati["ruolo"] = "magazziniere"
    risposta = client.post("/utenti", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 400
    assert risposta.json()["detail"] == "Inserire addetto o responsabile"

def test_inserisci_username_uguale():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    controllo = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 409
    assert controllo.json()["detail"] == "Username gia in uso"

def test_rimuovi_utente_senza_autorizzazione():
    risposta = client.delete("/utenti/2", headers={"Authorization": "Bearer token_non_autorizzato"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Richiesta negata"

def test_registra_e_cancella_utente():
    token = registra_e_login()
    conn = database.apri_connessione()
    cursore = conn.execute("SELECT id_utente FROM sessioni WHERE token = ?", (token, ))
    id_utente = cursore.fetchone()
    conn.close()
    risposta = client.delete(f"/utenti/{id_utente[0]}", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()["id"] == id_utente[0]
    controllo_rimozione = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": f"Bearer {token}"})
    assert controllo_rimozione.status_code == 401
    assert controllo_rimozione.json()["detail"] == "Token non valido"

def test_token_mancante_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Not authenticated"

def test_bearer_diverso_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    token = registra_e_login()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": f"Ciao {token}"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Not authenticated"

def test_token_non_valido_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token non valido"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Token non valido"

def test_token_scaduto_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer TOKEN_SCADUTO"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Token scaduto"

def test_nuovo_utente_password_corta():
    dati = UTENTE_VALIDO.copy()
    dati["password"] = "a" 
    risposta = client.post("/utenti", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "password"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_hash_utente():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    id_utente = risposta.json()["id"]
    conn = database.apri_connessione()
    cursore = conn.execute("SELECT hash FROM utenti WHERE id = ?", (id_utente, ))
    hash_utente = cursore.fetchone()
    conn.close()
    verifica = password_hash.verify(UTENTE_VALIDO["password"], hash_utente[0])
    assert verifica

def test_login_password_sbagliata():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    username = risposta.json()["username"]
    controllo = client.post("/login", json={"username": username, "password": "123456789"})
    assert controllo.status_code == 401
    assert controllo.json()["detail"] == "Credenziali non valide"

def test_login_corretto():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    username = risposta.json()["username"]
    password = UTENTE_VALIDO["password"]
    id_utente = risposta.json()["id"]
    controllo = client.post("/login", json={"username": username, "password": password})
    assert controllo.status_code == 200
    conn = database.apri_connessione()
    cursore = conn.execute("SELECT token FROM sessioni WHERE id_utente = ?", (id_utente, ))
    token = cursore.fetchone()
    conn.close()
    assert controllo.json()["token"] == token[0]

def test_login_username_inesistente():
    risposta = client.post("/login", json={"username": "inesistente", "password": "cane12345"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Credenziali non valide"

def test_login_senza_hash(): # -> L'utente valido non è registrato a sistem quindi non ha le credenziali x login
    risposta = client.post("/login", json={"username": UTENTE_VALIDO["username"], "password": "cane1234"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Credenziali non valide"

def test_prova_funzione_fixture_aggiungi_prodotto():
    risposta = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})    
    assert risposta.status_code == 200
    id_nuovo_prodotto = risposta.json()["id"]
    assert risposta.json()["Prodotto"]["nome"] == PRODOTTO_VALIDO["nome"]
    richiesta_nuovo = client.get(f"/catalogo/{id_nuovo_prodotto}", headers={"Authorization": "Bearer token_autorizzato"})
    assert richiesta_nuovo.status_code == 200
    assert richiesta_nuovo.json()["id"] == id_nuovo_prodotto
### FUNZIONE DI PROVA PER IL FIXTURE
def test_get_prodotto_cancellato_funzione_fixture():
    risposta = client.get("/catalogo/4", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_utente_corto():
    risposta = client.post("/utenti", json = {"nome": "a", "password": "cane12345"}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "nome"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_aggiungi_articolo_nome_corto():
    dati = PRODOTTO_VALIDO.copy()
    dati["nome"] = "a"
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "nome"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_aggiungi_articolo_prezzo_zero():
    dati = PRODOTTO_VALIDO.copy()
    dati["prezzo"] = 0
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "prezzo"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_aggiungi_articolo_categoria_corta():
    dati = PRODOTTO_VALIDO.copy()
    dati["categoria"] = "a"
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "categoria"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_aggiungi_articolo_quantita_zero():
    dati = PRODOTTO_VALIDO.copy()
    dati["quantita"] = 0
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "quantita"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_trova_prodotto_id_inesistente():
    risposta = client.get("/catalogo/9999", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_rimuovi_prodotto_id_inesistente():
    risposta = client.delete("/catalogo/99999", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_rimuovi_prodotto_senza_autorizzazione():
    risposta = client.delete("/catalogo/3", headers={"Authorization": "Bearer token_non_autorizzato"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Richiesta negata"

def test_modifica_articolo_id_inesistente():
    risposta = client.patch("/catalogo/99999", json={}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_modifica_articolo_non_autorizzato():
    risposta = client.patch("/catalogo/1", json={"quantita": 5}, headers={"Authorization": "Bearer token_non_autorizzato"})
    assert risposta.status_code == 403

def test_modifica_articolo_nome_corto():
    risposta = client.patch("/catalogo/1", json={"nome" : "a"}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "nome"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_modifica_articolo_prezzo_zero():
    risposta = client.patch("/catalogo/1", json={"prezzo" : 0}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "prezzo"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_modifica_articolo_categoria_corto():
    risposta = client.patch("/catalogo/1", json={"categoria" : "a"}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "categoria"]
    assert risposta.json()["detail"][0]["type"] == "string_too_short"

def test_trova_prodotti_categoria():
    risposta = client.get("/catalogo?categoria=mouse", headers={"Authorization": "Bearer token_autorizzato"})
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["categoria"] == "mouse"

def test_trova_prodotti_filtro_prezzo():
    risposta = client.get("/catalogo?prezzo_inferiore_a=50", headers={"Authorization": "Bearer token_autorizzato"})
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["prezzo"]<=50

def test_carico_quantita_valida():
    risposta = client.patch("/catalogo/1/carico", json={"quantita": 5}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()[1]["quantita"] == 5

def test_carica_quantita_id_inesistente():
    risposta = client.patch("/catalogo/9999/carico" , json={"quantita": 5}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_carica_quantita_zero():
    risposta = client.patch("/catalogo/1/carico" , json={"quantita": 0}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "quantita"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_preleva_quantita_id_inesistente():
    risposta = client.patch("/catalogo/9999/prelievo" , json={"quantita": 5}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_preleva_quantita_zero():
    risposta = client.patch("/catalogo/1/prelievo" , json={"quantita": 0}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 422
    assert risposta.json()["detail"][0]["loc"] == ["body", "quantita"]
    assert risposta.json()["detail"][0]["type"] == "greater_than"

def test_preleva_quantita_maggiore_di_stock():
    richiesta_giacenza = client.get("/catalogo/2", headers={"Authorization": "Bearer token_autorizzato"})
    assert richiesta_giacenza.status_code == 200
    giacenza = richiesta_giacenza.json()["quantita"]
    risposta = client.patch("/catalogo/2/prelievo" , json={"quantita": 9999}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()[0]["quantita"] == 0
    assert risposta.json()[0]["mancanti"] == 9999 - giacenza
    assert risposta.json()[1]["quantita"] == giacenza

def test_movimenti_completo_filtro_data():
    solo_data=data.split(" ")[0]
    risposta = client.get(f"/movimenti?data={solo_data}", headers={"Authorization": "Bearer token_autorizzato"})
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["data_movimento"].split(" ")[0] == solo_data

def test_movimenti_utente_inesistente():
    risposta = client.get("/movimenti/9999", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_movimenti_filtro_carico():
    risposta = client.get("/movimenti/1?tipo_movimenti=carico", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    dati = risposta.json()["movimenti"]
    assert dati!= []
    for riga in dati:
        assert riga["movimento"] == "carico"

def test_mostra_utenti():
    risposta = client.get("/utenti", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json() != []
    assert risposta.json()[0]["nome"] =="Leon"

def test_mostra_utenti_non_autorizzato():
    risposta = client.get("/utenti", headers={"Authorization": "Bearer token_non_autorizzato"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Richiesta negata"

def test_inserimenti_prodotto_valido():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    id_nuovo_prodotto = risposta.json()["id"]
    rilettura = client.get(f"/catalogo/{id_nuovo_prodotto}", headers={"Authorization": "Bearer token_autorizzato"})
    assert rilettura.status_code == 200
    assert rilettura.json()["id"] == id_nuovo_prodotto
    assert rilettura.json()["nome"] == PRODOTTO_VALIDO["nome"]

def test_rimuovi_utente_inesistente():
    risposta = client.delete("/utenti/9999", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_trova_utente_id_inesistente():
    risposta = client.get("/utenti/9999", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_rimuovi_utente_con_movimenti():
    risposta = client.delete("/utenti/2", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "Impossibile eliminare l'utente: presenta dei movimenti"
    controllo = client.get("/utenti/1", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 200
    assert controllo.json()["id"] == 1

def test_rimuovi_utente_senza_movimenti():
    risposta = client.delete("/utenti/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()["id"] == 3
    controllo = client.get("/utenti/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 404
    assert controllo.json()["detail"] == "Utente non trovato"

def test_rimuovi_articolo_con_movimenti():
    risposta = client.delete("/catalogo/1", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "Impossibile eliminare il prodotto: presenta dei movimenti"
    controllo = client.get("/catalogo/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 200
    assert controllo.json()["id"] == 3

def test_rimuovi_articolo_senza_movimenti():
    risposta = client.delete("/catalogo/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()["id"] == 3
    controllo = client.get("/catalogo/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 404
    assert controllo.json()["detail"] == "Articolo non trovato"