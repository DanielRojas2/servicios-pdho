import enum
from datetime import date, datetime
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EstadoFormulario(str, enum.Enum):
    """Estados del ciclo de vida de los formularios mensuales."""
    BORRADOR = "BORRADOR"
    ENVIADO = "ENVIADO"
    OBSERVADO = "OBSERVADO"
    APROBADO = "APROBADO"


class EstadisticaHotelera(Base):
    """
    Modelo ORM para el formulario oficial departamental de Estadísticas Hoteleras.
    Representa el instrumento físico 'ESTADÍSTICAS HOTELERAS' con número correlativo en rojo.
    """
    __tablename__ = "estadisticas_hoteleras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    numero_formulario: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    id_establecimiento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    mes: Mapped[str] = mapped_column(String(20), nullable=False)
    gestion: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_presentacion: Mapped[date] = mapped_column(Date, nullable=False)

    # Sección B: Empleados
    cant_emp_perma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cant_emp_event: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_empleados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Archivos digitales
    archivo_foto: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archivo_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Estado del formulario
    estado: Mapped[EstadoFormulario] = mapped_column(
        SAEnum(EstadoFormulario, native_enum=False, length=20),
        default=EstadoFormulario.BORRADOR,
        nullable=False
    )

    # Cuadro Resumen (RN específicas requeridas)
    r_ingreso_nals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    r_ingreso_extr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    r_permanencia_nals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    r_permanencia_extr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_nals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_extr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_ing: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_perm: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    observaciones: Mapped[str | None] = mapped_column(String(500), nullable=True)

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    fecha_modificacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    # Restricciones de tabla
    __table_args__ = (
        UniqueConstraint("id_establecimiento", "mes", "gestion", name="uq_estadistica_hotelera_periodo"),
        CheckConstraint("r_ingreso_nals >= 0", name="chk_est_r_ing_nals_nonneg"),
        CheckConstraint("r_ingreso_extr >= 0", name="chk_est_r_ing_extr_nonneg"),
        CheckConstraint("r_permanencia_nals >= 0", name="chk_est_r_perm_nals_nonneg"),
        CheckConstraint("r_permanencia_extr >= 0", name="chk_est_r_perm_extr_nonneg"),
        CheckConstraint("cant_emp_perma >= 0", name="chk_est_emp_perma_nonneg"),
        CheckConstraint("cant_emp_event >= 0", name="chk_est_emp_event_nonneg"),
    )

    # Relaciones ORM
    establecimiento = relationship("Establecimiento")
    detalles = relationship(
        "DetalleEstadisticaHotelera",
        back_populates="estadistica",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<EstadisticaHotelera id={self.id} nro='{self.numero_formulario}' est_id={self.id_establecimiento} {self.mes}/{self.gestion}>"


class DetalleEstadisticaHotelera(Base):
    """
    Matriz dinámica dispersa de movimientos diarios por nacionalidad.
    Almacena exclusivamente las celdas con datos reales para evitar sobrecarga de ceros.
    """
    __tablename__ = "detalles_estadisticas_hoteleras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    id_estadistica: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("estadisticas_hoteleras.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    id_nacionalidad: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nacionalidades.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    dia: Mapped[int] = mapped_column(Integer, nullable=False)
    cant_ingresos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cant_permanencias: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("id_estadistica", "id_nacionalidad", "dia", name="uq_detalle_estadistica_celda"),
        CheckConstraint("dia >= 1 AND dia <= 31", name="chk_det_est_dia_range"),
        CheckConstraint("cant_ingresos >= 0", name="chk_det_est_ing_nonneg"),
        CheckConstraint("cant_permanencias >= 0", name="chk_det_est_perm_nonneg"),
    )

    estadistica = relationship("EstadisticaHotelera", back_populates="detalles")
    nacionalidad = relationship("Nacionalidad", lazy="joined")

    def __repr__(self) -> str:
        return f"<DetalleEstadisticaHotelera id={self.id} est_id={self.id_estadistica} nac_id={self.id_nacionalidad} dia={self.dia}>"


class OcupacionHotelera(Base):
    """
    Modelo ORM para el formulario oficial de Ocupación Hotelera (Instrumento físico 2).
    Registra habitaciones ocupadas por noche y cantidad de personas que las ocuparon.
    """
    __tablename__ = "ocupacion_hotelera"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    id_establecimiento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    mes: Mapped[str] = mapped_column(String(20), nullable=False)
    gestion: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_presentacion: Mapped[date] = mapped_column(Date, nullable=False)

    # Sumatorias del mes
    total_hab_ocupadas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_personas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Archivos digitales
    archivo_foto: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archivo_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Estado del formulario
    estado: Mapped[EstadoFormulario] = mapped_column(
        SAEnum(EstadoFormulario, native_enum=False, length=20),
        default=EstadoFormulario.BORRADOR,
        nullable=False
    )

    observaciones: Mapped[str | None] = mapped_column(String(500), nullable=True)

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    fecha_modificacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    __table_args__ = (
        UniqueConstraint("id_establecimiento", "mes", "gestion", name="uq_ocupacion_hotelera_periodo"),
        CheckConstraint("total_hab_ocupadas >= 0", name="chk_ocup_tot_hab_nonneg"),
        CheckConstraint("total_personas >= 0", name="chk_ocup_tot_pers_nonneg"),
    )

    establecimiento = relationship("Establecimiento")
    detalles = relationship(
        "DetalleOcupacionHotelera",
        back_populates="ocupacion",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<OcupacionHotelera id={self.id} est_id={self.id_establecimiento} {self.mes}/{self.gestion}>"


class DetalleOcupacionHotelera(Base):
    """
    Detalle diario disperso para Ocupación Hotelera (días 1 al 31).
    Solo almacena los días con ocupación real para optimizar la base de datos.
    """
    __tablename__ = "detalles_ocupacion_hotelera"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    id_ocupacion: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ocupacion_hotelera.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    dia: Mapped[int] = mapped_column(Integer, nullable=False)
    hab_ocupadas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cant_personas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("id_ocupacion", "dia", name="uq_detalle_ocupacion_dia"),
        CheckConstraint("dia >= 1 AND dia <= 31", name="chk_det_ocup_dia_range"),
        CheckConstraint("hab_ocupadas >= 0", name="chk_det_ocup_hab_nonneg"),
        CheckConstraint("cant_personas >= 0", name="chk_det_ocup_pers_nonneg"),
    )

    ocupacion = relationship("OcupacionHotelera", back_populates="detalles")

    def __repr__(self) -> str:
        return f"<DetalleOcupacionHotelera id={self.id} ocup_id={self.id_ocupacion} dia={self.dia}>"
