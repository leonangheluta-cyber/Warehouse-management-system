from dotenv import load_dotenv
from pathlib import Path
from app.security import password_hash
import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import apri_db, UtenteORM, engine


path_env = Path.home()/"Secret"/".env"
load_dotenv(dotenv_path=path_env)
password_gestionale = os.environ.get("PASSWORD_RESPONSABILE")
hash_password_gestionale = password_hash.hash(password_gestionale)

def inserisci_seed():
    with Session(engine) as session:
        query_responsabile = select(UtenteORM).where(UtenteORM.username == "leon.l")
        responsabile_trovato = session.scalars(query_responsabile).one_or_none()
        if responsabile_trovato is None:
            utente_responsabile = UtenteORM(nome = "Leon", hash_utente = hash_password_gestionale, username = "leon.l", ruolo = "responsabile")
            session.add(utente_responsabile)
            session.commit()
