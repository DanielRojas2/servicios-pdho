import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RolUsuario(str, enum.Enum):
    """Roles de usuario conforme a los lineamientos RBAC de AGETIC."""
    ADMIN_DEPARTAMENTAL = "ADMIN_DEPARTAMENTAL"
    OPERADOR_HOSPEDAJE = "OPERADOR_HOSPEDAJE"
    DEPENDIENTE_HOSPEDAJE = "DEPENDIENTE_HOSPEDAJE"


class Usuario(Base):
    """Modelo ORM para usuarios del sistema PDHO."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        SAEnum(RolUsuario, native_enum=False, length=50),
        default=RolUsuario.OPERADOR_HOSPEDAJE,
        nullable=False
    )
    id_establecimiento: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("establecimientos.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    credenciales_enviadas: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relación bidireccional con Establecimiento
    establecimiento = relationship("Establecimiento", back_populates="usuarios", foreign_keys=[id_establecimiento])

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email='{self.email}' rol='{self.rol}'>"
