from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenException
from app.modules.reportes.schemas import (
    CumplimientoDeclaracionesResponse,
    GraficoBarrasRankingResponse,
    GraficoTortaNacionalesExtranjerosResponse,
    PermanenciasVsIngresosResponse,
    TableroEjecutivoResponse,
)
from app.modules.reportes.service import ReportesService
from app.modules.usuarios.dependencies import get_current_active_user, require_roles
from app.modules.usuarios.models import RolUsuario, Usuario

router = APIRouter(prefix="/reportes", tags=["Módulo Administrativo y Reportes Estadísticos"])


def resolver_establecimiento_acceso(
    current_user: Usuario,
    id_establecimiento_solicitado: int | None
) -> int | None:
    """
    Garantiza el aislamiento multi-tenant:
    - Si el usuario es ADMIN_DEPARTAMENTAL, puede consultar el establecimiento solicitado o todos (None).
    - Si es OPERADOR o DEPENDIENTE, solo puede consultar su propio establecimiento.
    """
    if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL:
        return id_establecimiento_solicitado

    if not current_user.id_establecimiento:
        raise ForbiddenException("El usuario no tiene un establecimiento asignado.")

    if id_establecimiento_solicitado and id_establecimiento_solicitado != current_user.id_establecimiento:
        raise ForbiddenException("No tiene permisos para acceder a las estadísticas de otros establecimientos.")

    return current_user.id_establecimiento


# ========================================================
# 1. GRÁFICO DE TORTA: NACIONALES VS EXTRANJEROS
# ========================================================

@router.get(
    "/graficos/nacionales-extranjeros",
    response_model=GraficoTortaNacionalesExtranjerosResponse,
    status_code=status.HTTP_200_OK,
    summary="Gráfico de torta: Huéspedes nacionales vs extranjeros"
)
async def grafico_nacionales_extranjeros(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    fecha_inicio: Annotated[date | None, Query(description="Fecha inicio para filtro por días exactos")] = None,
    fecha_fin: Annotated[date | None, Query(description="Fecha fin para filtro por días exactos")] = None,
    mes: Annotated[str | None, Query(description="Nombre del mes en español (ej: 'septiembre')")] = None,
    gestion: Annotated[int | None, Query(description="Año o gestión a consultar (ej: 2026)")] = None,
    gestion_inicio: Annotated[int | None, Query(description="Año inicial para rango de gestiones")] = None,
    gestion_fin: Annotated[int | None, Query(description="Año final para rango de gestiones")] = None,
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (Solo Admin)")] = None,
    categoria: Annotated[str | None, Query(description="Categoría de hospedaje")] = None,
):
    """
    Genera la distribución porcentual y absoluta entre huéspedes bolivianos y extranjeros.
    Permite filtrar por rango de días exactos, por mes/gestión, por año único o por rango de años.
    """
    est_id = resolver_establecimiento_acceso(current_user, id_establecimiento)
    return await ReportesService.obtener_grafico_nacionales_extranjeros(
        db=db,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        mes=mes,
        gestion=gestion,
        gestion_inicio=gestion_inicio,
        gestion_fin=gestion_fin,
        id_establecimiento=est_id,
        categoria=categoria,
    )


# ========================================================
# 2. GRÁFICO DE BARRAS: RANKING DE NACIONALIDADES
# ========================================================

@router.get(
    "/graficos/nacionalidades-ranking",
    response_model=GraficoBarrasRankingResponse,
    status_code=status.HTTP_200_OK,
    summary="Gráfico de barras: Top 10 nacionalidades con más afluencia y resto"
)
async def grafico_ranking_nacionalidades(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    fecha_inicio: Annotated[date | None, Query(description="Fecha inicio para filtro por días exactos")] = None,
    fecha_fin: Annotated[date | None, Query(description="Fecha fin para filtro por días exactos")] = None,
    mes: Annotated[str | None, Query(description="Nombre del mes en español (ej: 'septiembre')")] = None,
    gestion: Annotated[int | None, Query(description="Año o gestión a consultar (ej: 2026)")] = None,
    gestion_inicio: Annotated[int | None, Query(description="Año inicial para rango de gestiones")] = None,
    gestion_fin: Annotated[int | None, Query(description="Año final para rango de gestiones")] = None,
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (Solo Admin)")] = None,
    categoria: Annotated[str | None, Query(description="Categoría de hospedaje")] = None,
    paises_ids: Annotated[list[int] | None, Query(description="IDs de países específicos a visualizar")] = None,
    codigos_pais: Annotated[list[str] | None, Query(description="Códigos ISO de países específicos a visualizar (ej: BO, AR)")] = None,
    incluir_resto: Annotated[bool, Query(description="Si es True, incluye la información del puesto 11 en adelante")] = True,
    skip_resto: Annotated[int, Query(description="Desplazamiento para paginar el resto de países (del 11 en adelante)")] = 0,
    limit_resto: Annotated[int, Query(description="Límite de registros para la cola del ranking")] = 50,
):
    """
    Retorna el listado de las 10 nacionalidades con más afluencia en el período y provee
    el listado de la posición 11 en adelante (resto), permitiendo seleccionar países específicos
    si el administrador requiere un análisis enfocado.
    """
    est_id = resolver_establecimiento_acceso(current_user, id_establecimiento)
    return await ReportesService.obtener_grafico_ranking_nacionalidades(
        db=db,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        mes=mes,
        gestion=gestion,
        gestion_inicio=gestion_inicio,
        gestion_fin=gestion_fin,
        id_establecimiento=est_id,
        categoria=categoria,
        paises_ids=paises_ids,
        codigos_pais=codigos_pais,
        incluir_resto=incluir_resto,
        skip_resto=skip_resto,
        limit_resto=limit_resto,
    )


# ========================================================
# 3. COMPARATIVA PERMANENCIAS (PERNOCTACIONES) VS INGRESOS
# ========================================================

@router.get(
    "/graficos/permanencias-vs-ingresos",
    response_model=PermanenciasVsIngresosResponse,
    status_code=status.HTTP_200_OK,
    summary="Comparativa de permanencias (pernoctaciones) vs llegadas (ingresos)"
)
async def grafico_permanencias_vs_ingresos(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    fecha_inicio: Annotated[date | None, Query(description="Fecha inicio para filtro por días exactos")] = None,
    fecha_fin: Annotated[date | None, Query(description="Fecha fin para filtro por días exactos")] = None,
    mes: Annotated[str | None, Query(description="Nombre del mes en español (ej: 'septiembre')")] = None,
    gestion: Annotated[int | None, Query(description="Año o gestión a consultar (ej: 2026)")] = None,
    gestion_inicio: Annotated[int | None, Query(description="Año inicial para rango de gestiones")] = None,
    gestion_fin: Annotated[int | None, Query(description="Año final para rango de gestiones")] = None,
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (Solo Admin)")] = None,
    categoria: Annotated[str | None, Query(description="Categoría de hospedaje")] = None,
    id_nacionalidad: Annotated[int | None, Query(description="ID de un país individual a analizar")] = None,
    cod_pais: Annotated[str | None, Query(description="Código ISO de un país individual (ej: BO o AR)")] = None,
    paises_ids: Annotated[list[int] | None, Query(description="Lista de IDs de países")] = None,
    codigos_pais: Annotated[list[str] | None, Query(description="Lista de códigos ISO de países")] = None,
    agrupar_por: Annotated[str, Query(description="'pais' (compara países) o 'tiempo' (evolución temporal)")] = "pais",
):
    """
    Compara pernoctaciones vs llegadas para un país particular o un rango/grupo de países seleccionados.
    Calcula el promedio de noches de permanencia por huésped para evaluar la estancia turística media.
    """
    est_id = resolver_establecimiento_acceso(current_user, id_establecimiento)
    return await ReportesService.obtener_permanencias_vs_ingresos(
        db=db,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        mes=mes,
        gestion=gestion,
        gestion_inicio=gestion_inicio,
        gestion_fin=gestion_fin,
        id_establecimiento=est_id,
        categoria=categoria,
        id_nacionalidad=id_nacionalidad,
        cod_pais=cod_pais,
        paises_ids=paises_ids,
        codigos_pais=codigos_pais,
        agrupar_por=agrupar_por,
    )


# ========================================================
# 4. TABLERO EJECUTIVO Y KPIS DEPARTAMENTALES
# ========================================================

@router.get(
    "/tablero-ejecutivo",
    response_model=TableroEjecutivoResponse,
    status_code=status.HTTP_200_OK,
    summary="Tablero ejecutivo: KPIs consolidados y tasa de ocupación departamental"
)
async def tablero_ejecutivo(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    fecha_inicio: Annotated[date | None, Query(description="Fecha inicio")] = None,
    fecha_fin: Annotated[date | None, Query(description="Fecha fin")] = None,
    mes: Annotated[str | None, Query(description="Nombre del mes")] = None,
    gestion: Annotated[int | None, Query(description="Gestión")] = None,
    gestion_inicio: Annotated[int | None, Query(description="Gestión inicio")] = None,
    gestion_fin: Annotated[int | None, Query(description="Gestión fin")] = None,
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (Solo Admin)")] = None,
    categoria: Annotated[str | None, Query(description="Categoría")] = None,
):
    """
    Retorna los indicadores de alto nivel institucional:
    - Cobertura de establecimientos declarantes.
    - Total de llegadas y pernoctaciones.
    - Tasa de ocupación ponderada departamental (%).
    - Estancia media en noches por visitante.
    """
    est_id = resolver_establecimiento_acceso(current_user, id_establecimiento)
    return await ReportesService.obtener_tablero_ejecutivo(
        db=db,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        mes=mes,
        gestion=gestion,
        gestion_inicio=gestion_inicio,
        gestion_fin=gestion_fin,
        id_establecimiento=est_id,
        categoria=categoria,
    )


# ========================================================
# 5. BITÁCORA DE CUMPLIMIENTO INSTITUCIONAL
# ========================================================

@router.get(
    "/cumplimiento-declaraciones",
    response_model=CumplimientoDeclaracionesResponse,
    status_code=status.HTTP_200_OK,
    summary="Bitácora de cumplimiento: Control de presentaciones mensuales"
)
async def cumplimiento_declaraciones(
    mes: Annotated[str, Query(description="Nombre del mes en español (ej: 'septiembre')")],
    gestion: Annotated[int, Query(description="Año a consultar (ej: 2026)")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
):
    """
    Listado centralizado para la administración departamental donde se verifica
    qué establecimientos ya enviaron sus formularios de estadísticas y ocupación,
    y cuáles permanecen pendientes u omisos.
    """
    return await ReportesService.obtener_cumplimiento_declaraciones(
        db=db,
        mes=mes,
        gestion=gestion,
    )


# ========================================================
# 6. EXPORTACIÓN DE DATOS A CSV
# ========================================================

@router.get(
    "/exportar/csv",
    status_code=status.HTTP_200_OK,
    summary="Descargar reporte consolidado en formato CSV"
)
async def exportar_reporte_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    mes: Annotated[str | None, Query(description="Mes")] = None,
    gestion: Annotated[int | None, Query(description="Gestión")] = None,
    gestion_inicio: Annotated[int | None, Query(description="Gestión inicial")] = None,
    gestion_fin: Annotated[int | None, Query(description="Gestión final")] = None,
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento")] = None,
    categoria: Annotated[str | None, Query(description="Categoría")] = None,
):
    """Genera y descarga un archivo CSV estructurado con codificación UTF-8 compatible con Microsoft Excel."""
    est_id = resolver_establecimiento_acceso(current_user, id_establecimiento)
    contenido_csv = await ReportesService.exportar_reporte_movimientos_csv(
        db=db,
        mes=mes,
        gestion=gestion,
        gestion_inicio=gestion_inicio,
        gestion_fin=gestion_fin,
        id_establecimiento=est_id,
        categoria=categoria,
    )

    filename = f"reporte_pdho_{gestion or 'general'}_{mes or 'anual'}.csv"

    return Response(
        content=contenido_csv,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8",
        }
    )
