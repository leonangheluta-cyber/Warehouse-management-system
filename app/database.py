import os
from fastapi import Depends
from sqlalchemy import create_engine, Numeric, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, Session, DeclarativeBase, relationship
from decimal import Decimal
from typing import Annotated

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PERCORSO_DB_ORM = os.path.join(CARTELLA, "gestionale_orm.db")

engine = create_engine(f"sqlite+pysqlite:///{PERCORSO_DB_ORM}", echo=True)

def apri_db():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(apri_db)]

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


def spacchetta_articolo(articolo):
    return {"id": articolo.id, "nome": articolo.nome, "prezzo": articolo.prezzo, "categoria": articolo.categoria, "quantita": articolo.quantita, "data_inserimento": articolo.data_inserimento, "data_ultimo_movimento": articolo.data_ultimo_movimento}


def spacchetta_movimento(movimento):
    return {"id_movimento": movimento.id, "id_utente": movimento.id_utente, "id_articolo": movimento.id_articolo, "quantita": movimento.quantita, "tipo": movimento.tipo, "data": movimento.data, "giacenza_post_movimento": movimento.giacenza_dopo_movimento}


def spacchetta_movimenti_completo(movimento):
    return {"id_movimento": movimento.id, "id_utente": movimento.id_utente, "nome_utente": movimento.utente.nome, "quantita": movimento.quantita, "movimento": movimento.tipo, "articolo": movimento.articolo.nome, "qta_post_movimento": movimento.giacenza_dopo_movimento, "data_movimento": movimento.data}