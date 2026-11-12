from pydantic import BaseModel, Field


class Articolo(BaseModel):
    nome: str = Field(min_length = 2)
    prezzo: float = Field(gt = 0)
    categoria: str = Field(min_length = 2)
    quantita: int = Field(gt = 0)

class ModificaArticolo(BaseModel):
    nome: str | None = Field(default = None, min_length = 2)
    prezzo: float | None = Field(default = None, gt = 0)
    categoria: str | None = Field(default = None, min_length = 2)

class CaricoPrelievo(BaseModel):
    quantita: int = Field(gt = 0)

class Utente(BaseModel):
    nome: str = Field(min_length = 2)
    username: str = Field(min_length=3, max_length=15)
    ruolo: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length = 8)

class LoginUtente(BaseModel):
    username: str 
    password: str 