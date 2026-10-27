from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Nacionalidad(Base):
    """
    Catálogo de nacionalidades y procedencias de huéspedes.
    Cumple con la norma ISO 3166-1 alfa-2 para códigos de países (RN-7).
    Incluye categorías agregadas especiales del formulario oficial (ej: 'Otros America', 'Otros Europa', 'Otros Asia', 'Otros').
    """
    __tablename__ = "nacionalidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    pais: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    cod_pais: Mapped[str] = mapped_column(String(4), unique=True, nullable=False, index=True)
    continente: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Nacionalidad id={self.id} pais='{self.pais}' cod='{self.cod_pais}'>"
