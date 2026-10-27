import re
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.usuarios.models import RolUsuario


def validate_password_strength(password: str) -> str:
    """Valida la robustez de la contraseña bajo directrices de AGETIC (PISI / ISO 27001)."""
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("La contraseña debe contener al menos una letra mayúscula.")
    if not re.search(r"[a-z]", password):
        raise ValueError("La contraseña debe contener al menos una letra minúscula.")
    if not re.search(r"\d", password):
        raise ValueError("La contraseña debe contener al menos un número.")
    if not re.search(r"[@$!%*?&#/._-]", password):
        raise ValueError("La contraseña debe contener al menos un carácter especial (@$!%*?&#/._-).")
    return password


class UserBase(BaseModel):
    email: EmailStr
    nombre_completo: str = Field(..., min_length=3, max_length=150)
    rol: RolUsuario = RolUsuario.OPERADOR_HOSPEDAJE
    id_establecimiento: int | None = Field(None, description="ID del establecimiento asociado si aplica.")


class UserCreate(UserBase):
    password: str | None = Field(
        None,
        description="Contraseña inicial del usuario. Si se omite, se generará una automáticamente."
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_password_strength(v)
        return v


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    nombre_completo: str | None = Field(None, min_length=3, max_length=150)
    rol: RolUsuario | None = None
    id_establecimiento: int | None = None
    activo: bool | None = None


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_pwd(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nombre_completo: str
    rol: RolUsuario
    id_establecimiento: int | None = None
    activo: bool
    credenciales_enviadas: bool
    fecha_creacion: datetime
    ultimo_login: datetime | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
