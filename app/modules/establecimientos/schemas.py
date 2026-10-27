from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.establecimientos.models import TipoHabitacionEnum
from app.modules.usuarios.schemas import UserResponse, validate_password_strength


# ---------------------------------------------------------------------------
# Schemas para Tipos de Habitación y Capacidad
# ---------------------------------------------------------------------------

class TipoHabitacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_habitacion: TipoHabitacionEnum
    descripcion: str | None = None


class HabitacionItemInput(BaseModel):
    id_tipo_habitacion: int = Field(..., description="ID del catálogo de TipoHabitacion")
    cant_habitaciones: int = Field(..., ge=0, description="Cantidad de habitaciones de este tipo")
    nro_camas: int = Field(..., ge=0, description="Número de camas asociadas a este tipo de habitación")


class HabitacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tipo_habitacion: int
    tipo_habitacion: str
    cant_habitaciones: int
    nro_camas: int


class CapacidadHabitacionesUpdate(BaseModel):
    habitaciones: list[HabitacionItemInput] = Field(
        ...,
        description="Lista de tipos de habitaciones y sus cantidades para actualizar la capacidad instalada."
    )


# ---------------------------------------------------------------------------
# Schemas para Establecimiento
# ---------------------------------------------------------------------------

class EstablecimientoBase(BaseModel):
    nombre_establecimiento: str = Field(..., min_length=3, max_length=150)
    direccion: str = Field(..., min_length=3, max_length=255)
    categoria: str = Field(..., min_length=2, max_length=50)
    latitud: float | None = Field(None, description="Coordenada geográfica de latitud (GPS)")
    longitud: float | None = Field(None, description="Coordenada geográfica de longitud (GPS)")
    telefono: str | None = Field(None, max_length=50)
    total_plazas: int = Field(default=0, ge=0, description="Total de plazas/camas ingresado manualmente por el establecimiento o admin")


class EstablecimientoCreateConOperador(EstablecimientoBase):
    """
    Schema utilizado por ADMIN_DEPARTAMENTAL para registrar simultáneamente
    un establecimiento y su usuario operador/administrador inicial.
    """
    operador_nombre_completo: str = Field(..., min_length=3, max_length=150)
    operador_email: EmailStr
    operador_password: str | None = Field(
        None,
        description="Contraseña del operador. Si se omite, se generará una automáticamente conforme a AGETIC."
    )

    @field_validator("operador_password")
    @classmethod
    def validate_pwd(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_password_strength(v)
        return v


class EstablecimientoUpdate(BaseModel):
    nombre_establecimiento: str | None = Field(None, min_length=3, max_length=150)
    direccion: str | None = Field(None, min_length=3, max_length=255)
    categoria: str | None = Field(None, min_length=2, max_length=50)
    latitud: float | None = None
    longitud: float | None = None
    telefono: str | None = None
    total_plazas: int | None = Field(None, ge=0)
    activo: bool | None = None


class EstablecimientoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_establecimiento: str
    direccion: str
    categoria: str
    latitud: float | None = None
    longitud: float | None = None
    telefono: str | None = None
    total_habitaciones: int
    total_plazas: int
    id_operador: int | None = None
    activo: bool
    fecha_registro: datetime
    operador: UserResponse | None = None
    habitaciones: list[HabitacionResponse] = []


# ---------------------------------------------------------------------------
# Schemas para Gestión de Dependientes (por el Operador)
# ---------------------------------------------------------------------------

class DependienteCreate(BaseModel):
    nombre_completo: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    password: str | None = Field(
        None,
        description="Contraseña inicial del dependiente. Si se omite, se generará una automáticamente."
    )

    @field_validator("password")
    @classmethod
    def validate_pwd(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_password_strength(v)
        return v


class DependienteUpdate(BaseModel):
    nombre_completo: str | None = Field(None, min_length=3, max_length=150)
    email: EmailStr | None = None
    activo: bool | None = None
