import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TipoHabitacionEnum(str, enum.Enum):
    """Tipos estándar de habitación según categorización hotelera departamental."""
    SUITE = "suite"
    MATRIMONIAL = "matrimonial"
    SIMPLE = "simple"
    DOBLE = "doble"
    TRIPLE = "triple"
    MULTIPLE = "multiple"


class TipoHabitacion(Base):
    """Catálogo de tipos de habitaciones hoteleras."""
    __tablename__ = "tipos_habitacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    tipo_habitacion: Mapped[TipoHabitacionEnum] = mapped_column(
        SAEnum(
            TipoHabitacionEnum,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj]
        ),
        unique=True,
        nullable=False,
        index=True
    )
    descripcion: Mapped[str | None] = mapped_column(String(100), nullable=True)

    habitaciones = relationship("Habitaciones", back_populates="tipo_habitacion")

    def __repr__(self) -> str:
        return f"<TipoHabitacion id={self.id} tipo='{self.tipo_habitacion}'>"


class Establecimiento(Base):
    """Modelo ORM para establecimientos de hospedaje en el departamento de Oruro."""
    __tablename__ = "establecimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    nombre_establecimiento: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    direccion: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    latitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Capacidad instalada: total_habitaciones suma de cant_habitaciones (RN-2).
    # total_plazas es autogestionado de forma manual por el establecimiento o admin.
    total_habitaciones: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_plazas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Identificador del usuario que funge como operador titular/administrador
    id_operador: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL", use_alter=True),
        unique=True,
        nullable=True
    )

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relaciones ORM
    operador = relationship(
        "Usuario",
        foreign_keys=[id_operador],
        post_update=True
    )
    usuarios = relationship(
        "Usuario",
        foreign_keys="[Usuario.id_establecimiento]",
        back_populates="establecimiento"
    )
    habitaciones = relationship(
        "Habitaciones",
        back_populates="establecimiento",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Establecimiento id={self.id} nombre='{self.nombre_establecimiento}' cat='{self.categoria}'>"


class Habitaciones(Base):
    """
    Capacidad discriminada por tipo de habitación para un establecimiento.
    Llave primaria compuesta por (id_establecimiento, id_tipo_habitacion) conforme a RN-3.
    """
    __tablename__ = "habitaciones"

    id_establecimiento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        primary_key=True
    )
    id_tipo_habitacion: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tipos_habitacion.id", ondelete="CASCADE"),
        primary_key=True
    )
    cant_habitaciones: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    nro_camas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relaciones ORM
    establecimiento = relationship("Establecimiento", back_populates="habitaciones")
    tipo_habitacion = relationship("TipoHabitacion", back_populates="habitaciones", lazy="joined")

    def __repr__(self) -> str:
        return f"<Habitaciones est_id={self.id_establecimiento} tipo_id={self.id_tipo_habitacion} cant={self.cant_habitaciones} camas={self.nro_camas}>"
