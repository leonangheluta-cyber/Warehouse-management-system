import sqlite3
import os
from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from pwdlib import PasswordHash
from sqlalchemy import select, create_engine, Numeric, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, Session, DeclarativeBase, relationship
from decimal import Decimal

schema_bearer = HTTPBearer()
password_hash = PasswordHash.recommended()
path_env = Path.home()/"Secret"/".env"
load_dotenv(dotenv_path=path_env)
password_gestionale = os.environ.get("PASSWORD_RESPONSABILE")
hash_password_gestionale = password_hash.hash(password_gestionale)

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB = os.path.join(CARTELLA, "script_gestionale_magazzino.db")
PERCORSO_DB_ORM = os.path.join(CARTELLA, "gestionale_orm.db")

engine = create_engine(f"sqlite+pysqlite:///{PERCORSO_DB_ORM}", echo=True)

@event.listens_for(engine, "connect")
def attiva_foreign_keys(connessione_dbapi, record_connessione):
    cursore = connessione_dbapi.cursor()
    cursore.execute("PRAGMA foreign_keys = ON")
    cursore.close()

class Base(DeclarativeBase):
    pass

class ArticoloORM(Base):
    __tablename__ = "articoli"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    prezzo: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    categoria: Mapped[str]
    quantita: Mapped[int]
    data_inserimento: Mapped[str]
    data_ultimo_movimento: Mapped[str] 
    movimenti: Mapped[list["MovimentoORM"]] = relationship(back_populates="articolo")

class UtenteORM(Base):
    __tablename__ = "utenti"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    hash_utente: Mapped[str] = mapped_column("hash")
    username: Mapped[str] = mapped_column(unique=True)
    ruolo: Mapped[str]
    movimenti: Mapped[list["MovimentoORM"]] = relationship(back_populates="utente")
    sessioni: Mapped[list["SessioneORM"]] = relationship(back_populates="utente", cascade="all, delete-orphan")

class MovimentoORM(Base):
    __tablename__ = "movimenti"
    id: Mapped[int] = mapped_column(primary_key=True)
    id_utente: Mapped[int] = mapped_column(ForeignKey("utenti.id"))
    id_articolo: Mapped[int] = mapped_column(ForeignKey("articoli.id"))
    quantita: Mapped[int]
    tipo: Mapped[str]
    data: Mapped[str]
    giacenza_dopo_movimento: Mapped[int] 
    utente: Mapped["UtenteORM"] = relationship(back_populates="movimenti")
    articolo: Mapped["ArticoloORM"] = relationship(back_populates="movimenti")

class SessioneORM(Base):
    __tablename__ = "sessioni"
    id_utente: Mapped[int] = mapped_column(ForeignKey("utenti.id"))
    token: Mapped[str] = mapped_column(primary_key=True)
    scadenza: Mapped[str]
    utente: Mapped["UtenteORM"] = relationship(back_populates="sessioni")

Base.metadata.create_all(engine)

with Session(engine) as session:
    query_responsabile = select(UtenteORM).where(UtenteORM.username == "leon.l")
    reaponsabile_trovato = session.scalars(query_responsabile).one_or_none()
    if reaponsabile_trovato is None:
        utente_responsabile = UtenteORM(nome = "Leon", hash_utente = hash_password_gestionale, username = "leon.l", ruolo = "responsabile")
        session.add(utente_responsabile)
        session.commit()
"""
def apri_connessione():
    conn=sqlite3.connect(PERCORSO_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
"""
def apri_db():
    with Session(engine) as session:
        yield session

def spacchetta_articolo(articolo):
    return {"id": articolo.id, "nome": articolo.nome, "prezzo": articolo.prezzo, "categoria": articolo.categoria, "quantita": articolo.quantita, "data_inserimento": articolo.data_inserimento, "data_ultimo_movimento": articolo.data_ultimo_movimento}

def spacchetta_riga_movimento(riga):
    return {"id_movimento": riga[0], "id_utente": riga[1], "id_articolo": riga[2], "quantita": riga[3], "tipo": riga[4], "data": riga[5], "giacenza_post_movimento": riga[6]}

def spacchetta_movimenti_completo(riga):
    return {"id_movimento": riga[0], "id_utente": riga[1], "nome_utente": riga[2], "quantita": riga[3], "movimento": riga[4], "articolo": riga[5], "qta_post_movimento": riga[6], "data_movimento": riga[7]}

def controlla_articolo(id_prodotto: int, session: Session = Depends(apri_db)):
    query_prodotto = select(ArticoloORM).where(ArticoloORM.id == id_prodotto)
    articolo_trovato = session.scalars(query_prodotto).one_or_none()
    if articolo_trovato is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return articolo_trovato

def controlla_utente(conn, id_utente):
    cursore=conn.execute("SELECT * FROM utenti WHERE id = ?", (id_utente, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return riga_selezionata

def controlla_movimento_prodotto(conn, id_prodotto):
    cursore=conn.execute("SELECT count(*) FROM movimenti WHERE id_articolo = ?", (id_prodotto, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata[0] > 0:
        raise HTTPException(status_code=409, detail="Impossibile eliminare il prodotto: presenta dei movimenti")

def controlla_movimento_utente(conn, id_utente):
    cursore=conn.execute("SELECT count(*) FROM movimenti WHERE id_utente = ?", (id_utente, ))
    riga_selezionata=cursore.fetchone()
    if riga_selezionata[0] > 0:
        raise HTTPException(status_code=409, detail="Impossibile eliminare l'utente: presenta dei movimenti")
    
def crea_movimento(conn, id_utente, id_articolo, quantita, tipo, giacenza_post_movimento):
    data=str(datetime.now().replace(microsecond=0))
    cursore=conn.execute("""INSERT INTO movimenti (id_utente, id_articolo, quantita, tipo, data, giacenza_dopo_movimento) VALUES (?, ?, ?, ?, ?, ?)""", (id_utente, id_articolo, quantita, tipo, data, giacenza_post_movimento))
    id_riga=cursore.lastrowid
    cursore_riga=conn.execute("SELECT * FROM movimenti WHERE id = ?", (id_riga, ))
    riga_movimento=cursore_riga.fetchone()
    riga_finale=spacchetta_riga_movimento(riga_movimento)
    return riga_finale

def controlla_token(credenziali: HTTPAuthorizationCredentials = Depends(schema_bearer), session: Session = Depends(apri_db)):
    token = credenziali.credentials
    query_sessione = select(SessioneORM).where(SessioneORM.token == token)
    sessione_trovata = session.scalars(query_sessione).one_or_none()
    if sessione_trovata is None:
        raise HTTPException(status_code=401, detail="Token non valido")
    scadenza = datetime.fromisoformat(sessione_trovata.scadenza)
    if scadenza > datetime.now().replace(microsecond=0):
        return sessione_trovata.id_utente
    else:
        raise HTTPException(status_code=401, detail="Token scaduto")

def controlla_ruolo_addetto_responsabile(id_utente: int = Depends(controlla_token), session: Session = Depends(apri_db)):
    query_utente = select(UtenteORM).where(UtenteORM.id == id_utente)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is not None:
        if utente_trovato.ruolo not in ["addetto", "responsabile"]:
            raise HTTPException(status_code=403, detail="Azione negata")
        else:
            return id_utente
    else:
        raise HTTPException(status_code=401, detail="Utente non trovato")

def controlla_ruolo_responsabile(id_utente: int = Depends(controlla_token), session: Session = Depends(apri_db)):
    query_responsabile = select(UtenteORM).where(UtenteORM.id == id_utente)
    responsabile_trovato = session.scalars(query_responsabile).one_or_none()
    if responsabile_trovato is not None:
        if responsabile_trovato.ruolo != "responsabile":
            raise HTTPException(status_code=403, detail="Azione negata")
        else:
            return id_utente
    else:
        raise HTTPException(status_code=401, detail="Utente non trovato")