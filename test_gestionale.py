from fastapi.testclient import TestClient
from gestionale import app

client=TestClient(app)

PRODOTTO_VALIDO={"nome": "Tappetino mouse", "prezzo": 15, "categoria": "mouse", "quantita": 25}

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
    risposta=client.post("/catalogo", json=dati)
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