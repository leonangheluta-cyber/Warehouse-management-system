from sqlalchemy.orm import Session
from sqlalchemy import create_engine, event
import os
from gestionale import app, apri_db, ArticoloORM, UtenteORM, MovimentoORM, SessioneORM
from database import password_hash, Base
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from pytest import raises
from sqlalchemy.exc import IntegrityError

client = TestClient(app)
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB = os.path.join(CARTELLA, "test_orm.db")
path_env = Path.home()/ "Secret" / ".env"
load_dotenv(dotenv_path=path_env)
password_responsabile = os.environ.get("PASSWORD_RESPONSABILE")
HASH_PASSWORD_RESPONSABILE = password_hash.hash(password_responsabile)

engine_test = create_engine(f"sqlite+pysqlite:///{PERCORSO_DB}")
data_test = str(datetime.now().replace(microsecond=0))
password_addetto_1 = password_hash .hash("cane12345")
password_addetto_2 = password_hash.hash("banana12345")

@event.listens_for(engine_test, "connect")
def attiva_pragma(connessione_dbapi, record_connessione):
    cursore = connessione_dbapi.cursor()
    cursore.execute("PRAGMA foreign_keys = ON")
    cursore.close()

Base.metadata.create_all(engine_test)

def apri_db_prova():
    with Session(engine_test) as session:
        yield session

app.dependency_overrides[apri_db] = apri_db_prova

def inserisci_dati_prova():
    with Session(engine_test) as session:
        nuovo_articolo_uno = ArticoloORM(nome = "Mouse da gaming", prezzo = 25, categoria = "mouse", quantita = 15, data_inserimento = data_test, data_ultimo_movimento = data_test)
        nuovo_articolo_due = ArticoloORM(nome = "Monitor LG 2k", prezzo = 250, categoria = "monitor", quantita = 24, data_inserimento = data_test, data_ultimo_movimento = data_test)
        nuovo_articolo_tre = ArticoloORM(nome = "Tastiera meccanica", prezzo = 25, categoria = "tastiera", quantita = 15, data_inserimento = data_test, data_ultimo_movimento = data_test)
        nuovo_utente_uno = UtenteORM(nome = "Leon", username = "leon.l", ruolo = "responsabile", hash_utente = HASH_PASSWORD_RESPONSABILE)
        nuovo_utente_due = UtenteORM(nome = "Mario", username = "mario.m", ruolo = "addetto", hash_utente = password_addetto_1)
        nuovo_utente_tre = UtenteORM(nome = "Franco", username = "franco.f", ruolo = "addetto", hash_utente = password_addetto_2)
        nuovo_movimento_uno = MovimentoORM(id_utente = 1, id_articolo = 1, quantita = 10, tipo = "carico", data = data_test, giacenza_dopo_movimento = 15)
        nuovo_movimento_due = MovimentoORM(id_utente = 1, id_articolo = 2, quantita = 10, tipo = "prelievo", data = data_test, giacenza_dopo_movimento = 24)
        nuovo_movimento_tre = MovimentoORM(id_utente = 2, id_articolo = 1, quantita = 10, tipo = "carico", data = data_test, giacenza_dopo_movimento = 24)
        nuova_sessione_uno = SessioneORM(id_utente = 1, token = "token_autorizzato", scadenza = "2030-10-10 00:00:00")
        nuova_sessione_due = SessioneORM(id_utente = 2, token = "token_scaduto", scadenza = "2000-10-10 00:00:00")
        session.add_all([nuovo_articolo_uno, nuovo_articolo_due, nuovo_articolo_tre, nuovo_utente_uno, nuovo_utente_due, nuovo_utente_tre, nuovo_movimento_uno, nuovo_movimento_due, nuovo_movimento_tre, nuova_sessione_uno, nuova_sessione_due])
        session.commit()

PRODOTTO_VALIDO = {"nome": "Tappetino mouse", "prezzo": 15, "categoria": "mouse", "quantita": 25}
UTENTE_VALIDO = {"nome": "Luigi", "username": "luigi.l", "ruolo": "addetto", "password": "password_inventata"}

@pytest.fixture(autouse=True)
def pulisci_db():
    Base.metadata.drop_all(engine_test)
    Base.metadata.create_all(engine_test)
    inserisci_dati_prova()
    yield
    Base.metadata.drop_all(engine_test)

# I PRIMI 2 TEST SONO PER VERIFICARE IL CORRETTO FUNZIONAMENTO DI FIXTURE

def test_prova_funzione_fixture_aggiungi_prodotto():
    risposta = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})    
    assert risposta.status_code == 200
    id_nuovo_prodotto = risposta.json()["articolo"]["id"]
    assert risposta.json()["articolo"]["nome"] == PRODOTTO_VALIDO["nome"]
    richiesta_nuovo = client.get(f"/catalogo/{id_nuovo_prodotto}", headers={"Authorization": "Bearer token_autorizzato"})
    assert richiesta_nuovo.status_code == 200
    assert richiesta_nuovo.json()["id"] == id_nuovo_prodotto

def test_get_prodotto_cancellato_funzione_fixture():
    risposta = client.get("/catalogo/4", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_foreign_key_nuovo_movimento_articolo_inesistente():
    with Session(engine_test) as session:
        nuovo_movimento = MovimentoORM(id_utente = 1, id_articolo = 9999, quantita = 10, tipo = "carico", data = data_test, giacenza_dopo_movimento = 15)
        session.add(nuovo_movimento)
        with pytest.raises(IntegrityError):
            session.commit()

def test_delete_nuovo_articolo_senza_movimenti_movimento_nuovo_articolo():
    nuovo = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert nuovo.status_code == 200
    id_nuovo = nuovo.json()["articolo"]["id"]
    rimozione = client.delete(f"/catalogo/{id_nuovo}", headers={"Authorization": "Bearer token_autorizzato"})
    assert rimozione.status_code == 200
    assert rimozione.json()["id"] == id_nuovo

def test_delete_nuovo_articolo_e_movimenti_carico():
    nuovo = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert nuovo.status_code == 200
    id_nuovo = nuovo.json()["articolo"]["id"]
    aggiunta = client.patch(f"/catalogo/{id_nuovo}/carico", json={"quantita": 1}, headers={"Authorization": "Bearer token_autorizzato"})
    assert aggiunta.status_code == 200
    rimozione = client.delete(f"/catalogo/{id_nuovo}", headers={"Authorization": "Bearer token_autorizzato"})
    assert rimozione.status_code == 409
    assert rimozione.json()["detail"] == "L'articolo presenta movimenti"

def test_post_articolo_movimento_nuovo_articolo():
    risposta = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()["movimento"]["tipo"] == "nuovo articolo"

def test_movimenti_per_prodotto():
    risposta = client.get("/catalogo/1/movimenti", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json() != []
    for movimento in risposta.json():
        assert movimento["id_articolo"] == 1

def test_movimenti_articolo_inesistente():
    risposta = client.get("/catalogo/9999/movimenti", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"
        
def test_ruolo_sbagliato():
    dati = UTENTE_VALIDO.copy()
    dati["ruolo"] = "magazziniere"
    risposta = client.post("/utenti", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 400
    assert risposta.json()["detail"] == "Inserire addetto o responsabile"

def test_username_gia_preso():
    dati = UTENTE_VALIDO.copy()
    dati["username"] = "mario.m"
    risposta = client.post("/utenti", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "Username gia presente"

def test_rimuovi_utente_senza_autorizzazione():
    login = client.post("/login", json={"username": "franco.f", "password": "banana12345"})
    token = login.json()["token"]
    risposta = client.delete("/utenti/2", headers={"Authorization": f"Bearer {token}"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Azione negata"

def test_registra_e_cancella_utente_e_aggiunta_prodotto_utente_cancellato():
    registrazione = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert registrazione.status_code == 200
    id_utente = registrazione.json()["id_utente"]
    login = client.post("/login", json={"username": UTENTE_VALIDO["username"], "password": UTENTE_VALIDO["password"]})
    assert login.status_code == 200
    token = login.json()["token"]
    cancellazione = client.delete(f"/utenti/{id_utente}", headers={"Authorization": "Bearer token_autorizzato"})
    assert cancellazione.status_code == 200
    assert cancellazione.json()["utente_eliminato"]["id"] == id_utente
    prova = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": f"Bearer {token}"})
    assert prova.status_code == 401
    assert prova.json()["detail"] == "Token non valido"

def test_token_mancante_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati)
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Not authenticated"

def test_bearer_diverso_rotta_aggiungi_articolo():
    risposta = client.post("/catalogo", json=PRODOTTO_VALIDO, headers={"Authorization": "Ciao token_autorizzato"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Not authenticated"

def test_token_non_valido_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token non valido"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Token non valido"

def test_token_scaduto_rotta_aggiungi_articolo():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_scaduto"})
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
    id_utente = risposta.json()["id_utente"]
    with Session(engine_test) as session:
        utente = session.get(UtenteORM, id_utente)
    verifica = password_hash.verify(UTENTE_VALIDO["password"], utente.hash_utente)
    assert verifica

def test_login_password_sbagliata():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    username = risposta.json()["username"]
    controllo = client.post("/login", json={"username": username, "password": "123456789"})
    assert controllo.status_code == 401
    assert controllo.json()["detail"] == "Credenziali non valide"

def test_aggiungi_utente_e_login_corretti():
    risposta = client.post("/utenti", json=UTENTE_VALIDO, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    username = risposta.json()["username"]
    password = UTENTE_VALIDO["password"]
    controllo = client.post("/login", json={"username": username, "password": password})
    assert controllo.status_code == 200

def test_login_username_inesistente():
    risposta = client.post("/login", json={"username": "inesistente", "password": "cane12345"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Credenziali non valide"

def test_login_senza_hash(): # -> L'utente valido non è registrato a sistem quindi non ha le credenziali x login
    risposta = client.post("/login", json={"username": UTENTE_VALIDO["username"], "password": "cane1234"})
    assert risposta.status_code == 401
    assert risposta.json()["detail"] == "Credenziali non valide"

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
    login = client.post("login", json={"username": "mario.m", "password": "cane12345"})
    token = login.json()["token"]
    risposta = client.delete("/catalogo/3", headers={"Authorization": f"Bearer {token}"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Azione negata"

def test_modifica_articolo_id_inesistente():
    risposta = client.patch("/catalogo/99999", json={}, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Articolo non trovato"

def test_modifica_articolo_non_autorizzato():
    login = client.post("login", json={"username": "mario.m", "password": "cane12345"})
    token = login.json()["token"]
    risposta = client.patch("/catalogo/1", json={"quantita": 5}, headers={"Authorization": f"Bearer {token}"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Azione negata"

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
    assert risposta.json()["movimento"]["quantita"] == 5

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
    assert risposta.json()["articolo"]["quantita"] == 0
    assert risposta.json()["da_prelevare"] == 9999 - giacenza
    assert risposta.json()["movimento"]["quantita"] == giacenza

def test_movimenti_completo_filtro_data():
    solo_data = data_test.split()[0]
    risposta = client.get(f"/movimenti?data={solo_data}", headers={"Authorization": "Bearer token_autorizzato"})
    dati = risposta.json()
    assert risposta.status_code == 200
    assert dati != []
    for riga in dati:
        assert riga["data_movimento"].split()[0] == solo_data

def test_data_inesistente():
    risposta = client.get("/movimenti?data=2030-10-10", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json() == []
    

def test_movimenti_utente_inesistente():
    risposta = client.get("/movimenti/9999", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 404
    assert risposta.json()["detail"] == "Utente non trovato"

def test_movimenti_filtro_carico():
    risposta = client.get("/movimenti/1?tipo_movimenti=carico", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    dati = risposta.json()
    assert dati!= []
    for riga in dati:
        assert riga["tipo"] == "carico"

def test_mostra_utenti():
    risposta = client.get("/utenti", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json() != []
    assert risposta.json()[0]["nome"] =="Leon"

def test_mostra_utenti_non_autorizzato():
    login = client.post("/login", json={"username": "mario.m", "password": "cane12345"})
    token = login.json()["token"]
    risposta = client.get("/utenti", headers={"Authorization": f"Bearer {token}"})
    assert risposta.status_code == 403
    assert risposta.json()["detail"] == "Azione negata"

def test_inserimenti_prodotto_valido():
    dati = PRODOTTO_VALIDO.copy()
    risposta = client.post("/catalogo", json=dati, headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    id_nuovo_prodotto = risposta.json()["articolo"]["id"]
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
    assert risposta.json()["detail"] == "L'utente presenta movimenti"
    controllo = client.get("/utenti/2", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 200
    assert controllo.json()["id"] == 2

def test_rimuovi_utente_senza_movimenti():
    risposta = client.delete("/utenti/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()["utente_eliminato"]["id"] == 3
    controllo = client.get("/utenti/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 404
    assert controllo.json()["detail"] == "Utente non trovato"

def test_rimuovi_articolo_con_movimenti():
    risposta = client.delete("/catalogo/1", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "L'articolo presenta movimenti"
    controllo = client.get("/catalogo/1", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 200
    assert controllo.json()["id"] == 1

def test_rimuovi_articolo_senza_movimenti():
    risposta = client.delete("/catalogo/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert risposta.status_code == 200
    assert risposta.json()["id"] == 3
    controllo = client.get("/catalogo/3", headers={"Authorization": "Bearer token_autorizzato"})
    assert controllo.status_code == 404
    assert controllo.json()["detail"] == "Articolo non trovato"