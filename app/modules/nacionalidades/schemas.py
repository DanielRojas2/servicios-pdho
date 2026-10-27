from pydantic import BaseModel, ConfigDict, Field, field_validator


class NacionalidadBase(BaseModel):
    pais: str = Field(..., min_length=2, max_length=100, description="Nombre del país o procedencia")
    cod_pais: str = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Código ISO 3166-1 alfa-2 o código de región oficial (ej: BO, AR, XAM)"
    )
    continente: str | None = Field(None, max_length=50, description="Continente o región geográfica de clasificación")
    activo: bool = Field(default=True, description="Indica si la nacionalidad está habilitada para selección")

    @field_validator("cod_pais")
    @classmethod
    def normalizar_codigo(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("pais")
    @classmethod
    def normalizar_pais(cls, v: str) -> str:
        return v.strip()


class NacionalidadCreate(NacionalidadBase):
    """Schema para creación manual de una nueva nacionalidad por el administrador."""
    pass


class NacionalidadUpdate(BaseModel):
    """Schema para modificación parcial de datos de una nacionalidad."""
    pais: str | None = Field(None, min_length=2, max_length=100)
    cod_pais: str | None = Field(None, min_length=2, max_length=4)
    continente: str | None = Field(None, max_length=50)
    activo: bool | None = None

    @field_validator("cod_pais")
    @classmethod
    def normalizar_codigo(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip().upper()
        return v

    @field_validator("pais")
    @classmethod
    def normalizar_pais(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v


class NacionalidadResponse(NacionalidadBase):
    """Schema de respuesta para representación de nacionalidades."""
    model_config = ConfigDict(from_attributes=True)

    id: int


class NacionalidadSeedSummary(BaseModel):
    """Resumen de ejecución del proceso de poblamiento (seeding) del catálogo."""
    total_registros_procesados: int
    nuevos_insertados: int
    existentes_omitidos: int
    total_catalogo: int
