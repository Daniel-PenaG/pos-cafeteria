from pydantic import BaseModel


class UserCreate(BaseModel):
    nombre: str
    usuario_login: str
    password: str
    rol: str

class UserLogin(BaseModel):
    usuario_login: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"