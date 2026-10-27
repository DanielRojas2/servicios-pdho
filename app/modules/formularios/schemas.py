from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.formularios.models import EstadoFormulario


# ==========================================
# PERÍODOS Y CALENDARIO DINÁMICO
# ==========================================

class MesDisponibleResponse(BaseModel):
    """Información dinámica de meses según calendario real."""
    mes: str
    numero_mes: int
    dias_en_mes: int
    declarado: bool
    permitido: bool
    formulario_id: int | None = None


class PeriodosDisponiblesResponse(BaseModel):
    gestion: int
    meses: list[MesDisponibleResponse]


# ==========================================
# SUB-ESQUEMAS DE MAPEO (SECCIONES A y C)
# ==========================================

class SeccionAMapeada(BaseModel):
    """Mapeo automático de datos del establecimiento (Sección A) sin duplicación en BD."""
    nombre_establecimiento: str
    direccion: str
    categoria: str
    ciudad: str = "Oruro"
    telefono: str | None = None


class TipoHabitacionMapeada(BaseModel):
    tipo_habitacion: str
    cant_habitaciones: int
    nro_camas: int


class SeccionCMapeada(BaseModel):
    """Mapeo de capacidad instalada del establecimiento (Sección C)."""
    habitaciones: list[TipoHabitacionMapeada] = []
    total_habitaciones: int
    total_plazas: int


# ==========================================
# RESUMEN MATEMÁTICO (ESTADÍSTICAS HOTELERAS)
# ==========================================

class ResumenEstadistica(BaseModel):
    """Cuadro de resumen oficial con validación estricta de sumatorias cruzadas."""
    r_ingreso_nals: int = Field(0, ge=0, description="Ingreso de huéspedes nacionales (Bolivia)")
    r_ingreso_extr: int = Field(0, ge=0, description="Ingreso de huéspedes extranjeros")
    r_permanencia_nals: int = Field(0, ge=0, description="Pernoctaciones de huéspedes nacionales (Bolivia)")
    r_permanencia_extr: int = Field(0, ge=0, description="Pernoctaciones de huéspedes extranjeros")
    
    total_nals: int = Field(0, ge=0, description="Suma automática r_ingreso_nals + r_permanencia_nals")
    total_extr: int = Field(0, ge=0, description="Suma automática r_ingreso_extr + r_permanencia_extr")
    total_ing: int = Field(0, ge=0, description="Suma automática r_ingreso_nals + r_ingreso_extr")
    total_perm: int = Field(0, ge=0, description="Suma automática r_permanencia_nals + r_permanencia_extr")
    total: int = Field(0, ge=0, description="Total general que debe cuadrar horizontal y verticalmente")

    @model_validator(mode="after")
    def validar_cuadratura(self) -> "ResumenEstadistica":
        # Recálculo / validación de consistencia
        calc_total_nals = self.r_ingreso_nals + self.r_permanencia_nals
        calc_total_extr = self.r_ingreso_extr + self.r_permanencia_extr
        calc_total_ing = self.r_ingreso_nals + self.r_ingreso_extr
        calc_total_perm = self.r_permanencia_nals + self.r_permanencia_extr
        
        suma_vertical = calc_total_nals + calc_total_extr
        suma_horizontal = calc_total_ing + calc_total_perm

        if suma_vertical != suma_horizontal:
            raise ValueError(
                f"Descuadre en el resumen: Suma vertical de nacionales + extranjeros ({suma_vertical}) "
                f"no coincide con la suma horizontal de ingresos + permanencias ({suma_horizontal})."
            )
        
        self.total_nals = calc_total_nals
        self.total_extr = calc_total_extr
        self.total_ing = calc_total_ing
        self.total_perm = calc_total_perm
        self.total = suma_vertical
        return self


# ==========================================
# DETALLES Y MATRIZ DISPERSA
# ==========================================

class DetalleEstadisticaInput(BaseModel):
    """Celda con movimiento diario por nacionalidad para la matriz dinámica."""
    dia: int = Field(..., ge=1, le=31, description="Día del mes (1 al 31)")
    id_nacionalidad: int = Field(..., description="ID de la nacionalidad")
    cant_ingresos: int = Field(0, ge=0, description="Cantidad de ingresos (I)")
    cant_permanencias: int = Field(0, ge=0, description="Cantidad de permanencias (P)")


class DetalleEstadisticaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dia: int
    id_nacionalidad: int
    pais: str | None = None
    cod_pais: str | None = None
    cant_ingresos: int
    cant_permanencias: int


# ==========================================
# ESQUEMAS: ESTADÍSTICAS HOTELERAS
# ==========================================

class EstadisticaHoteleraPreviewResponse(BaseModel):
    """
    Respuesta del pipeline de reconocimiento de imagen para Estadísticas Hoteleras.
    Permite al usuario hotelero revisar y editar cada valor antes de enviar en limpio.
    """
    numero_formulario: str = Field(..., description="Correlativo detectado en rojo (ej. '000360')")
    mes: str = Field(..., description="Mes detectado (ej. 'Agosto')")
    gestion: int = Field(..., description="Año / gestión detectada (ej. 2026)")
    fecha_presentacion: date
    cant_emp_perma: int = 0
    cant_emp_event: int = 0
    total_empleados: int = 0
    
    archivo_foto: str | None = None
    archivo_pdf: str | None = None

    seccion_a: SeccionAMapeada
    seccion_c: SeccionCMapeada
    
    # Matriz dispersa detectada
    matriz_detalles: list[DetalleEstadisticaInput] = []
    
    # Resumen calculado
    resumen: ResumenEstadistica
    advertencias: list[str] = []


class EstadisticaHoteleraCreate(BaseModel):
    """
    Payload definitivo para guardar la declaración de Estadísticas Hoteleras en limpio.
    El usuario puede haber ajustado o corregido cualquiera de estos valores.
    """
    numero_formulario: str = Field(..., min_length=1, max_length=20, description="Número correlativo (ej: '000360')")
    mes: str = Field(..., min_length=3, max_length=20)
    gestion: int = Field(..., ge=2000, le=2100)
    fecha_presentacion: date
    
    cant_emp_perma: int = Field(0, ge=0)
    cant_emp_event: int = Field(0, ge=0)
    
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    
    # Matriz de celdas con datos (sparse)
    detalles: list[DetalleEstadisticaInput] = Field(default_factory=list)
    observaciones: str | None = None
    enviar_en_limpio: bool = Field(True, description="Si es True, el estado se guarda como ENVIADO; si es False, como BORRADOR")


class RespaldoAdjuntoResponse(BaseModel):
    """Respuesta de la subida y conversión de imagen de respaldo a PDF."""
    archivo_foto: str
    archivo_pdf: str
    mensaje: str = "Respaldo digitalizado y transformado a PDF con éxito."


class EstadisticaHoteleraUpdate(BaseModel):
    """Permite al operador o dependiente editar una declaración."""
    numero_formulario: str | None = None
    mes: str | None = None
    gestion: int | None = None
    fecha_presentacion: date | None = None
    cant_emp_perma: int | None = None
    cant_emp_event: int | None = None
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    detalles: list[DetalleEstadisticaInput] | None = None
    observaciones: str | None = None
    estado: EstadoFormulario | None = None


class EstadisticaHoteleraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero_formulario: str
    id_establecimiento: int
    mes: str
    gestion: int
    fecha_presentacion: date
    cant_emp_perma: int
    cant_emp_event: int
    total_empleados: int
    
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    estado: EstadoFormulario
    
    r_ingreso_nals: int
    r_ingreso_extr: int
    r_permanencia_nals: int
    r_permanencia_extr: int
    total_nals: int
    total_extr: int
    total_ing: int
    total_perm: int
    total: int
    
    observaciones: str | None = None
    fecha_creacion: datetime
    fecha_modificacion: datetime | None = None

    seccion_a: SeccionAMapeada | None = None
    seccion_c: SeccionCMapeada | None = None
    detalles: list[DetalleEstadisticaResponse] = []


# ==========================================
# ESQUEMAS: OCUPACIÓN HOTELERA
# ==========================================

class DetalleOcupacionInput(BaseModel):
    """Registro diario para el formulario de Ocupación Hotelera."""
    dia: int = Field(..., ge=1, le=31)
    hab_ocupadas: int = Field(0, ge=0, description="Habitaciones ocupadas por noche")
    cant_personas: int = Field(0, ge=0, description="Número de personas que las ocuparon")


class DetalleOcupacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dia: int
    hab_ocupadas: int
    cant_personas: int


class OcupacionHoteleraPreviewResponse(BaseModel):
    """Respuesta de previsualización para Ocupación Hotelera."""
    mes: str
    gestion: int
    fecha_presentacion: date
    total_hab_ocupadas: int = 0
    total_personas: int = 0
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    
    detalles: list[DetalleOcupacionInput] = []
    advertencias: list[str] = []


class OcupacionHoteleraCreate(BaseModel):
    """Payload para confirmar y guardar Ocupación Hotelera en limpio."""
    mes: str = Field(..., min_length=3, max_length=20)
    gestion: int = Field(..., ge=2000, le=2100)
    fecha_presentacion: date
    
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    
    detalles: list[DetalleOcupacionInput] = Field(default_factory=list)
    observaciones: str | None = None
    enviar_en_limpio: bool = Field(True, description="Si True, estado=ENVIADO; si False, BORRADOR")


class OcupacionHoteleraUpdate(BaseModel):
    """Edición de formulario de Ocupación Hotelera."""
    mes: str | None = None
    gestion: int | None = None
    fecha_presentacion: date | None = None
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    detalles: list[DetalleOcupacionInput] | None = None
    observaciones: str | None = None
    estado: EstadoFormulario | None = None


class OcupacionHoteleraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_establecimiento: int
    mes: str
    gestion: int
    fecha_presentacion: date
    total_hab_ocupadas: int
    total_personas: int
    archivo_foto: str | None = None
    archivo_pdf: str | None = None
    estado: EstadoFormulario
    observaciones: str | None = None
    fecha_creacion: datetime
    fecha_modificacion: datetime | None = None
    detalles: list[DetalleOcupacionResponse] = []
