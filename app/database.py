import os
from fastapi import Depends
from sqlalchemy import create_engine, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, Session, DeclarativeBase, relationship
from decimal import Decimal
from typing import Annotated
from dotenv import load_dotenv
from pathlib import Path

patch_env = Path.home() / "Secret" / ".env"
load_dotenv(dotenv_path=patch_env)
PERCORSO_POSTGRE_GESTIONALE = os.environ.get("POSTGRE_GESTIONALE_ADDETTO")

engine = create_engine(PERCORSO_POSTGRE_GESTIONALE, echo=True)

def apri_db():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(apri_db)]

#------ ORM classes ------

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

