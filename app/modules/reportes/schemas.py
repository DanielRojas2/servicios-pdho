from datetime import date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# ESQUEMAS GENERALES DE PERÍODO Y FILTROS
# ==========================================

class PeriodoReporte(BaseModel):
    """Metadatos del período consultado en el reporte estadístico."""
    tipo_filtro: str = Field(..., description="rango_fechas | mes_gestion | rango_gestiones | general")
    descripcion: str
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    mes: str | None = None
    gestion: int | None = None
    gestion_inicio: int | None = None
    gestion_fin: int | None = None


# ==========================================
# 1. GRÁFICO DE TORTA: NACIONALES VS EXTRANJEROS
# ==========================================

class SegmentoHuespedes(BaseModel):
    """Métricas agregadas para un segmento de huéspedes (Nacionales o Extranjeros)."""
    pais: str | None = None
    cod_pais: str | None = None
    cant_ingresos: int = Field(0, description="Total de llegadas registradas")
    cant_permanencias: int = Field(0, description="Total de noches de permanencia")
    total: int = Field(0, description="Suma de ingresos y permanencias")
    porcentaje_ingresos: float = Field(0.0, description="Porcentaje respecto al total de ingresos")
    porcentaje_permanencias: float = Field(0.0, description="Porcentaje respecto al total de permanencias")
    porcentaje_total: float = Field(0.0, description="Porcentaje respecto a la afluencia total")


class TotalesHuespedes(BaseModel):
    """Sumatorias generales del período para el gráfico de torta."""
    total_ingresos: int = 0
    total_permanencias: int = 0
    total_general: int = 0


class GraficoTortaNacionalesExtranjerosResponse(BaseModel):
    """Respuesta estructurada para el gráfico de torta nacional vs extranjero."""
    periodo: PeriodoReporte
    totales_generales: TotalesHuespedes
    nacionales: SegmentoHuespedes
    extranjeros: SegmentoHuespedes


# ==========================================
# 2. GRÁFICO DE BARRAS: RANKING DE NACIONALIDADES
# ==========================================

class NacionalidadRankingItem(BaseModel):
    """Detalle de afluencia por nacionalidad clasificada en el ranking."""
    ranking: int = Field(..., description="Posición en el ranking (1, 2, ...)")
    id_nacionalidad: int
    pais: str
    cod_pais: str
    continente: str | None = None
    cant_ingresos: int = 0
    cant_permanencias: int = 0
    total_afluencia: int = Field(0, description="Suma de ingresos + permanencias")
    porcentaje_del_total: float = Field(0.0, description="Participación porcentual en la afluencia total")


class TotalesAfluenciaPeriodo(BaseModel):
    """Totales de control del período consultado."""
    total_ingresos: int = 0
    total_permanencias: int = 0
    total_general: int = 0


class PaginacionResto(BaseModel):
    """Información de paginación para el bloque del 11 en adelante."""
    total_items_resto: int = 0
    skip: int = 0
    limit: int = 50


class GraficoBarrasRankingResponse(BaseModel):
    """
    Respuesta estructurada para el gráfico de barras.
    Separa el Top 10 y provee la información del 11 en adelante (resto).
    """
    periodo: PeriodoReporte
    total_paises_con_movimiento: int
    criterio_orden: str = "total_afluencia"
    top_10: list[NacionalidadRankingItem] = Field(default_factory=list)
    resto: list[NacionalidadRankingItem] = Field(default_factory=list)
    resto_paginacion: PaginacionResto | None = None
    totales_periodo: TotalesAfluenciaPeriodo


# ==========================================
# 3. PERMANENCIAS VS INGRESOS
# ==========================================

class SerieComparativaItem(BaseModel):
    """Punto de comparación entre permanencias e ingresos."""
    etiqueta: str = Field(..., description="Nombre del país o identificador de fecha/mes")
    codigo: str | None = None
    id_nacionalidad: int | None = None
    ingresos: int = 0
    permanencias: int = 0
    total: int = 0
    ratio_permanencia_ingreso: float = Field(
        0.0,
        description="Noches promedio por huésped (permanencias / ingresos)"
    )


class TotalesComparativa(BaseModel):
    total_ingresos: int = 0
    total_permanencias: int = 0
    promedio_general_noches: float = 0.0


class PermanenciasVsIngresosResponse(BaseModel):
    """Respuesta comparativa de pernoctaciones vs llegadas."""
    periodo: PeriodoReporte
    agrupacion: str = Field(..., description="'pais' (compara países) o 'tiempo' (evolución temporal)")
    filtro_paises_aplicado: list[str] | None = None
    series: list[SerieComparativaItem] = Field(default_factory=list)
    totales: TotalesComparativa


# ==========================================
# 4. TABLERO EJECUTIVO Y KPIS
# ==========================================

class TableroEjecutivoResponse(BaseModel):
    """Métricas e indicadores clave a nivel departamental para toma de decisiones."""
    periodo: PeriodoReporte
    establecimientos_registrados: int
    establecimientos_declarantes: int
    porcentaje_cobertura_establecimientos: float
    total_formularios_declarados: int
    total_ingresos: int
    total_permanencias: int
    total_huespedes: int
    total_habitaciones_ofertadas: int
    total_habitaciones_ocupadas: int
    tasa_ocupacion_porcentaje: float
    estadia_media_noches: float


# ==========================================
# 5. BITÁCORA DE CUMPLIMIENTO INSTITUCIONAL
# ==========================================

class EstablecimientoCumplimientoItem(BaseModel):
    """Estado de presentación mensual por establecimiento de hospedaje."""
    model_config = ConfigDict(from_attributes=True)

    id_establecimiento: int
    nombre_establecimiento: str
    categoria: str
    telefono: str | None = None
    tiene_estadistica: bool
    id_estadistica: int | None = None
    estado_estadistica: str | None = None
    tiene_ocupacion: bool
    id_ocupacion: int | None = None
    estado_ocupacion: str | None = None
    cumplimiento_completo: bool


class CumplimientoDeclaracionesResponse(BaseModel):
    """Reporte administrativo de cumplimiento y omisión de declaraciones."""
    mes: str
    gestion: int
    total_establecimientos: int
    total_al_dia: int
    total_pendientes: int
    porcentaje_cumplimiento: float
    establecimientos: list[EstablecimientoCumplimientoItem]
