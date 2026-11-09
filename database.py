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
    def __repr__(self):
        return f"Nome articolo: {self.nome} | Prezzo: {self.prezzo} | Categoria: {self.categoria} | Quantita: {self.quantita} | Data inserimento: {self.data_inserimento} | Data ultimo movimento: {self.data_ultimo_movimento}"
    
class UtenteORM(Base):
    __tablename__ = "utenti"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    hash_utente: Mapped[str] = mapped_column("hash")
    username: Mapped[str] = mapped_column(unique=True)
    ruolo: Mapped[str]
    movimenti: Mapped[list["MovimentoORM"]] = relationship(back_populates="utente")
    sessioni: Mapped[list["SessioneORM"]] = relationship(back_populates="utente", cascade="all, delete-orphan")
    def __repr__(self):
        return f"Nome: {self.nome} | Username: {self.username} | Ruolo: {self.ruolo}"

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

def apri_db():
    with Session(engine) as session:
        yield session

def spacchetta_articolo(articolo):
    return {"id": articolo.id, "nome": articolo.nome, "prezzo": articolo.prezzo, "categoria": articolo.categoria, "quantita": articolo.quantita, "data_inserimento": articolo.data_inserimento, "data_ultimo_movimento": articolo.data_ultimo_movimento}

def spacchetta_movimento(movimento):
    return {"id_movimento": movimento.id, "id_utente": movimento.id_utente, "id_articolo": movimento.id_articolo, "quantita": movimento.quantita, "tipo": movimento.tipo, "data": movimento.data, "giacenza_post_movimento": movimento.giacenza_dopo_movimento}

def spacchetta_movimenti_completo(movimento):
    return {"id_movimento": movimento.id, "id_utente": movimento.id_utente, "nome_utente": movimento.utente.nome, "quantita": movimento.quantita, "movimento": movimento.tipo, "articolo": movimento.articolo.nome, "qta_post_movimento": movimento.giacenza_dopo_movimento, "data_movimento": movimento.data}

def controlla_articolo(id_prodotto: int, session: Session = Depends(apri_db)):
    query_prodotto = select(ArticoloORM).where(ArticoloORM.id == id_prodotto)
    articolo_trovato = session.scalars(query_prodotto).one_or_none()
    if articolo_trovato is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return articolo_trovato

def controlla_utente(id_utente: int, session: Session = Depends(apri_db)):
    query_utente = select(UtenteORM).where(UtenteORM.id == id_utente)
    utente_trovato = session.scalars(query_utente).one_or_none()
    if utente_trovato is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return utente_trovato
    
def crea_movimento(id_utente_movimento, id_articolo_movimento, quantita_movimento, tipo_movimento, data_movimento, giacenza_post):
    nuovo_movimento = MovimentoORM(id_utente = id_utente_movimento, id_articolo = id_articolo_movimento, quantita = quantita_movimento, tipo = tipo_movimento, data = data_movimento, giacenza_dopo_movimento = giacenza_post)
    return nuovo_movimento

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