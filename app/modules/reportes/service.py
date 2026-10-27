import calendar
import csv
import io
from datetime import date
from typing import Any
from sqlalchemy import case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.establecimientos.models import Establecimiento
from app.modules.formularios.models import (
    DetalleEstadisticaHotelera,
    DetalleOcupacionHotelera,
    EstadisticaHotelera,
    EstadoFormulario,
    OcupacionHotelera,
)
from app.modules.nacionalidades.models import Nacionalidad
from app.modules.reportes.schemas import (
    CumplimientoDeclaracionesResponse,
    EstablecimientoCumplimientoItem,
    GraficoBarrasRankingResponse,
    GraficoTortaNacionalesExtranjerosResponse,
    NacionalidadRankingItem,
    PaginacionResto,
    PeriodoReporte,
    PermanenciasVsIngresosResponse,
    SegmentoHuespedes,
    SerieComparativaItem,
    TableroEjecutivoResponse,
    TotalesAfluenciaPeriodo,
    TotalesComparativa,
    TotalesHuespedes,
)

MESES_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

MES_NUM_A_NOMBRE = {v: k.capitalize() for k, v in MESES_MAP.items()}


class ReportesService:
    """Servicio de consolidación estadística y reportes analíticos de alto rendimiento."""

    # ========================================================
    # HELPERS DE PERÍODO Y FILTROS SQL
    # ========================================================

    @staticmethod
    def _crear_mes_case_expression():
        """Genera una expresión CASE dialecto-agnóstica (PostgreSQL y SQLite) para mapear mes a número."""
        return case(
            (func.lower(EstadisticaHotelera.mes) == "enero", 1),
            (func.lower(EstadisticaHotelera.mes) == "febrero", 2),
            (func.lower(EstadisticaHotelera.mes) == "marzo", 3),
            (func.lower(EstadisticaHotelera.mes) == "abril", 4),
            (func.lower(EstadisticaHotelera.mes) == "mayo", 5),
            (func.lower(EstadisticaHotelera.mes) == "junio", 6),
            (func.lower(EstadisticaHotelera.mes) == "julio", 7),
            (func.lower(EstadisticaHotelera.mes) == "agosto", 8),
            (func.lower(EstadisticaHotelera.mes) == "septiembre", 9),
            (func.lower(EstadisticaHotelera.mes) == "octubre", 10),
            (func.lower(EstadisticaHotelera.mes) == "noviembre", 11),
            (func.lower(EstadisticaHotelera.mes) == "diciembre", 12),
            else_=1
        )

    @staticmethod
    def _crear_mes_case_ocupacion():
        """Genera una expresión CASE para OcupacionHotelera."""
        return case(
            (func.lower(OcupacionHotelera.mes) == "enero", 1),
            (func.lower(OcupacionHotelera.mes) == "febrero", 2),
            (func.lower(OcupacionHotelera.mes) == "marzo", 3),
            (func.lower(OcupacionHotelera.mes) == "abril", 4),
            (func.lower(OcupacionHotelera.mes) == "mayo", 5),
            (func.lower(OcupacionHotelera.mes) == "junio", 6),
            (func.lower(OcupacionHotelera.mes) == "julio", 7),
            (func.lower(OcupacionHotelera.mes) == "agosto", 8),
            (func.lower(OcupacionHotelera.mes) == "septiembre", 9),
            (func.lower(OcupacionHotelera.mes) == "octubre", 10),
            (func.lower(OcupacionHotelera.mes) == "noviembre", 11),
            (func.lower(OcupacionHotelera.mes) == "diciembre", 12),
            else_=1
        )

    @classmethod
    def normalizar_periodo(
        cls,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        mes: str | None = None,
        gestion: int | None = None,
        gestion_inicio: int | None = None,
        gestion_fin: int | None = None,
    ) -> PeriodoReporte:
        """Determina la descripción y estructura tipada del período consultado."""
        if fecha_inicio and fecha_fin:
            if fecha_inicio > fecha_fin:
                raise BadRequestException("La fecha de inicio no puede ser posterior a la fecha de fin.")
            return PeriodoReporte(
                tipo_filtro="rango_fechas",
                descripcion=f"Del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}",
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
            )
        
        if mes and gestion:
            mes_clean = mes.strip().lower()
            if mes_clean not in MESES_MAP:
                raise BadRequestException(f"Mes no válido: '{mes}'. Debe ser un nombre de mes en español.")
            return PeriodoReporte(
                tipo_filtro="mes_gestion",
                descripcion=f"{mes_clean.capitalize()} {gestion}",
                mes=mes_clean,
                gestion=gestion,
            )

        if gestion_inicio and gestion_fin:
            if gestion_inicio > gestion_fin:
                raise BadRequestException("La gestión de inicio no puede ser superior a la gestión de fin.")
            return PeriodoReporte(
                tipo_filtro="rango_gestiones",
                descripcion=f"Gestiones {gestion_inicio} - {gestion_fin}",
                gestion_inicio=gestion_inicio,
                gestion_fin=gestion_fin,
            )

        if gestion:
            return PeriodoReporte(
                tipo_filtro="gestion_unica",
                descripcion=f"Gestión {gestion}",
                gestion=gestion,
            )

        # Si no se envía ningún parámetro, por defecto se toma el año en curso
        current_year = date.today().year
        return PeriodoReporte(
            tipo_filtro="general",
            descripcion=f"Gestión actual {current_year}",
            gestion=current_year,
        )

    # ========================================================
    # 1. GRÁFICO DE TORTA: NACIONALES VS EXTRANJEROS
    # ========================================================

    @classmethod
    async def obtener_grafico_nacionales_extranjeros(
        cls,
        db: AsyncSession,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        mes: str | None = None,
        gestion: int | None = None,
        gestion_inicio: int | None = None,
        gestion_fin: int | None = None,
        id_establecimiento: int | None = None,
        categoria: str | None = None,
    ) -> GraficoTortaNacionalesExtranjerosResponse:
        """
        Calcula la distribución de huéspedes nacionales (Bolivia) vs extranjeros.
        Optimizado: si es por mes/gestión usa el resumen precalculado; si es por días exactos usa los detalles.
        """
        periodo = cls.normalizar_periodo(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            mes=mes,
            gestion=gestion,
            gestion_inicio=gestion_inicio,
            gestion_fin=gestion_fin,
        )

        estados_validos = [EstadoFormulario.ENVIADO, EstadoFormulario.APROBADO]

        # VÍA A: FILTRO POR RANGO DE DÍAS EXACTOS (Consulta sobre DetalleEstadisticaHotelera)
        if periodo.tipo_filtro == "rango_fechas":
            mes_case = cls._crear_mes_case_expression()
            fecha_num = EstadisticaHotelera.gestion * 10000 + mes_case * 100 + DetalleEstadisticaHotelera.dia
            f_ini_num = fecha_inicio.year * 10000 + fecha_inicio.month * 100 + fecha_inicio.day
            f_fin_num = fecha_fin.year * 10000 + fecha_fin.month * 100 + fecha_fin.day

            cond_nacional = or_(
                Nacionalidad.cod_pais == "BO",
                func.lower(Nacionalidad.pais) == "bolivia"
            )

            stmt = (
                select(
                    func.coalesce(func.sum(case((cond_nacional, DetalleEstadisticaHotelera.cant_ingresos), else_=0)), 0).label("nals_ing"),
                    func.coalesce(func.sum(case((cond_nacional, DetalleEstadisticaHotelera.cant_permanencias), else_=0)), 0).label("nals_perm"),
                    func.coalesce(func.sum(case((~cond_nacional, DetalleEstadisticaHotelera.cant_ingresos), else_=0)), 0).label("extr_ing"),
                    func.coalesce(func.sum(case((~cond_nacional, DetalleEstadisticaHotelera.cant_permanencias), else_=0)), 0).label("extr_perm"),
                )
                .join(EstadisticaHotelera, DetalleEstadisticaHotelera.id_estadistica == EstadisticaHotelera.id)
                .join(Nacionalidad, DetalleEstadisticaHotelera.id_nacionalidad == Nacionalidad.id)
                .where(
                    EstadisticaHotelera.estado.in_(estados_validos),
                    fecha_num >= f_ini_num,
                    fecha_num <= f_fin_num,
                )
            )

            if id_establecimiento:
                stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
            if categoria:
                stmt = stmt.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
                stmt = stmt.where(Establecimiento.categoria == categoria)

            res = await db.execute(stmt)
            nals_ing, nals_perm, extr_ing, extr_perm = res.one()

        # VÍA B: FILTRO POR MES, GESTIÓN O RANGO DE GESTIONES (Consulta ultrarrápida sobre EstadisticaHotelera)
        else:
            stmt = (
                select(
                    func.coalesce(func.sum(EstadisticaHotelera.r_ingreso_nals), 0).label("nals_ing"),
                    func.coalesce(func.sum(EstadisticaHotelera.r_permanencia_nals), 0).label("nals_perm"),
                    func.coalesce(func.sum(EstadisticaHotelera.r_ingreso_extr), 0).label("extr_ing"),
                    func.coalesce(func.sum(EstadisticaHotelera.r_permanencia_extr), 0).label("extr_perm"),
                )
                .where(EstadisticaHotelera.estado.in_(estados_validos))
            )

            if periodo.tipo_filtro == "mes_gestion":
                stmt = stmt.where(
                    func.lower(EstadisticaHotelera.mes) == periodo.mes,
                    EstadisticaHotelera.gestion == periodo.gestion,
                )
            elif periodo.tipo_filtro == "rango_gestiones":
                stmt = stmt.where(
                    EstadisticaHotelera.gestion >= periodo.gestion_inicio,
                    EstadisticaHotelera.gestion <= periodo.gestion_fin,
                )
            elif periodo.gestion:
                stmt = stmt.where(EstadisticaHotelera.gestion == periodo.gestion)

            if id_establecimiento:
                stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
            if categoria:
                stmt = stmt.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
                stmt = stmt.where(Establecimiento.categoria == categoria)

            res = await db.execute(stmt)
            nals_ing, nals_perm, extr_ing, extr_perm = res.one()

        # Cálculos de totales y porcentajes
        total_nals = nals_ing + nals_perm
        total_extr = extr_ing + extr_perm
        tot_ingresos = nals_ing + extr_ing
        tot_permanencias = nals_perm + extr_perm
        tot_general = total_nals + total_extr

        pct_nals_ing = round((nals_ing / tot_ingresos * 100), 2) if tot_ingresos > 0 else 0.0
        pct_extr_ing = round((extr_ing / tot_ingresos * 100), 2) if tot_ingresos > 0 else 0.0

        pct_nals_perm = round((nals_perm / tot_permanencias * 100), 2) if tot_permanencias > 0 else 0.0
        pct_extr_perm = round((extr_perm / tot_permanencias * 100), 2) if tot_permanencias > 0 else 0.0

        pct_nals_tot = round((total_nals / tot_general * 100), 2) if tot_general > 0 else 0.0
        pct_extr_tot = round((total_extr / tot_general * 100), 2) if tot_general > 0 else 0.0

        return GraficoTortaNacionalesExtranjerosResponse(
            periodo=periodo,
            totales_generales=TotalesHuespedes(
                total_ingresos=tot_ingresos,
                total_permanencias=tot_permanencias,
                total_general=tot_general,
            ),
            nacionales=SegmentoHuespedes(
                pais="Bolivia",
                cod_pais="BO",
                cant_ingresos=nals_ing,
                cant_permanencias=nals_perm,
                total=total_nals,
                porcentaje_ingresos=pct_nals_ing,
                porcentaje_permanencias=pct_nals_perm,
                porcentaje_total=pct_nals_tot,
            ),
            extranjeros=SegmentoHuespedes(
                pais="Extranjeros",
                cod_pais=None,
                cant_ingresos=extr_ing,
                cant_permanencias=extr_perm,
                total=total_extr,
                porcentaje_ingresos=pct_extr_ing,
                porcentaje_permanencias=pct_extr_perm,
                porcentaje_total=pct_extr_tot,
            ),
        )

    # ========================================================
    # 2. GRÁFICO DE BARRAS: RANKING DE NACIONALIDADES
    # ========================================================

    @classmethod
    async def obtener_grafico_ranking_nacionalidades(
        cls,
        db: AsyncSession,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        mes: str | None = None,
        gestion: int | None = None,
        gestion_inicio: int | None = None,
        gestion_fin: int | None = None,
        id_establecimiento: int | None = None,
        categoria: str | None = None,
        paises_ids: list[int] | None = None,
        codigos_pais: list[str] | None = None,
        incluir_resto: bool = True,
        skip_resto: int = 0,
        limit_resto: int = 50,
    ) -> GraficoBarrasRankingResponse:
        """
        Retorna el ranking de nacionalidades por afluencia (ingresos + permanencias).
        Divide automáticamente el Top 10 y el resto (posiciones 11 en adelante).
        Permite filtrar por países específicos si el administrador así lo desea.
        """
        periodo = cls.normalizar_periodo(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            mes=mes,
            gestion=gestion,
            gestion_inicio=gestion_inicio,
            gestion_fin=gestion_fin,
        )

        estados_validos = [EstadoFormulario.ENVIADO, EstadoFormulario.APROBADO]

        ingresos_sum = func.coalesce(func.sum(DetalleEstadisticaHotelera.cant_ingresos), 0)
        perm_sum = func.coalesce(func.sum(DetalleEstadisticaHotelera.cant_permanencias), 0)
        total_afluencia_expr = (ingresos_sum + perm_sum)

        stmt = (
            select(
                Nacionalidad.id,
                Nacionalidad.pais,
                Nacionalidad.cod_pais,
                Nacionalidad.continente,
                ingresos_sum.label("cant_ingresos"),
                perm_sum.label("cant_permanencias"),
                total_afluencia_expr.label("total_afluencia"),
            )
            .join(DetalleEstadisticaHotelera, Nacionalidad.id == DetalleEstadisticaHotelera.id_nacionalidad)
            .join(EstadisticaHotelera, DetalleEstadisticaHotelera.id_estadistica == EstadisticaHotelera.id)
            .where(EstadisticaHotelera.estado.in_(estados_validos))
            .group_by(
                Nacionalidad.id,
                Nacionalidad.pais,
                Nacionalidad.cod_pais,
                Nacionalidad.continente,
            )
            .having(total_afluencia_expr > 0)
            .order_by(total_afluencia_expr.desc(), ingresos_sum.desc(), Nacionalidad.pais.asc())
        )

        # Filtros temporales
        if periodo.tipo_filtro == "rango_fechas":
            mes_case = cls._crear_mes_case_expression()
            fecha_num = EstadisticaHotelera.gestion * 10000 + mes_case * 100 + DetalleEstadisticaHotelera.dia
            f_ini_num = fecha_inicio.year * 10000 + fecha_inicio.month * 100 + fecha_inicio.day
            f_fin_num = fecha_fin.year * 10000 + fecha_fin.month * 100 + fecha_fin.day
            stmt = stmt.where(fecha_num >= f_ini_num, fecha_num <= f_fin_num)
        elif periodo.tipo_filtro == "mes_gestion":
            stmt = stmt.where(
                func.lower(EstadisticaHotelera.mes) == periodo.mes,
                EstadisticaHotelera.gestion == periodo.gestion,
            )
        elif periodo.tipo_filtro == "rango_gestiones":
            stmt = stmt.where(
                EstadisticaHotelera.gestion >= periodo.gestion_inicio,
                EstadisticaHotelera.gestion <= periodo.gestion_fin,
            )
        elif periodo.gestion:
            stmt = stmt.where(EstadisticaHotelera.gestion == periodo.gestion)

        # Filtros de establecimiento
        if id_establecimiento:
            stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
        if categoria:
            stmt = stmt.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
            stmt = stmt.where(Establecimiento.categoria == categoria)

        # Filtro de países seleccionados por el administrador
        if paises_ids:
            stmt = stmt.where(Nacionalidad.id.in_(paises_ids))
        if codigos_pais:
            cods_upper = [c.strip().upper() for c in codigos_pais if c.strip()]
            if cods_upper:
                stmt = stmt.where(func.upper(Nacionalidad.cod_pais).in_(cods_upper))

        filas = (await db.execute(stmt)).all()

        # Calcular sumatorias de todo el período filtrado
        tot_ingresos = sum(f.cant_ingresos for f in filas)
        tot_permanencias = sum(f.cant_permanencias for f in filas)
        tot_general = sum(f.total_afluencia for f in filas)

        # Construir items clasificados con porcentaje y posición
        ranking_items: list[NacionalidadRankingItem] = []
        for idx, f in enumerate(filas, start=1):
            pct = round((f.total_afluencia / tot_general * 100), 2) if tot_general > 0 else 0.0
            ranking_items.append(
                NacionalidadRankingItem(
                    ranking=idx,
                    id_nacionalidad=f.id,
                    pais=f.pais,
                    cod_pais=f.cod_pais,
                    continente=f.continente,
                    cant_ingresos=f.cant_ingresos,
                    cant_permanencias=f.cant_permanencias,
                    total_afluencia=f.total_afluencia,
                    porcentaje_del_total=pct,
                )
            )

        top_10 = ranking_items[:10]
        resto_completo = ranking_items[10:] if incluir_resto else []

        # Paginación del resto si aplica
        paginacion_resto: PaginacionResto | None = None
        if incluir_resto and len(resto_completo) > 0:
            paginacion_resto = PaginacionResto(
                total_items_resto=len(resto_completo),
                skip=skip_resto,
                limit=limit_resto,
            )
            resto_paginado = resto_completo[skip_resto : skip_resto + limit_resto]
        else:
            resto_paginado = []

        return GraficoBarrasRankingResponse(
            periodo=periodo,
            total_paises_con_movimiento=len(ranking_items),
            criterio_orden="total_afluencia",
            top_10=top_10,
            resto=resto_paginado,
            resto_paginacion=paginacion_resto,
            totales_periodo=TotalesAfluenciaPeriodo(
                total_ingresos=tot_ingresos,
                total_permanencias=tot_permanencias,
                total_general=tot_general,
            ),
        )

    # ========================================================
    # 3. COMPARATIVA PERMANENCIAS (PERNOCTACIONES) VS INGRESOS
    # ========================================================

    @classmethod
    async def obtener_permanencias_vs_ingresos(
        cls,
        db: AsyncSession,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        mes: str | None = None,
        gestion: int | None = None,
        gestion_inicio: int | None = None,
        gestion_fin: int | None = None,
        id_establecimiento: int | None = None,
        categoria: str | None = None,
        id_nacionalidad: int | None = None,
        cod_pais: str | None = None,
        paises_ids: list[int] | None = None,
        codigos_pais: list[str] | None = None,
        agrupar_por: str = "pais",  # 'pais' o 'tiempo'
    ) -> PermanenciasVsIngresosResponse:
        """
        Compara llegadas (ingresos) contra pernoctaciones (permanencias) y calcula
        la estadía media en noches por huésped (ratio permanencia/ingreso).
        """
        periodo = cls.normalizar_periodo(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            mes=mes,
            gestion=gestion,
            gestion_inicio=gestion_inicio,
            gestion_fin=gestion_fin,
        )

        estados_validos = [EstadoFormulario.ENVIADO, EstadoFormulario.APROBADO]

        # Consolidar filtros de países
        lista_ids = set(paises_ids or [])
        if id_nacionalidad:
            lista_ids.add(id_nacionalidad)

        lista_cods = {c.strip().upper() for c in (codigos_pais or []) if c.strip()}
        if cod_pais:
            lista_cods.add(cod_pais.strip().upper())

        ingresos_sum = func.coalesce(func.sum(DetalleEstadisticaHotelera.cant_ingresos), 0)
        perm_sum = func.coalesce(func.sum(DetalleEstadisticaHotelera.cant_permanencias), 0)

        series: list[SerieComparativaItem] = []
        tot_ing = 0
        tot_perm = 0

        # MODO 1: AGRUPAR POR PAÍS (Compara los países entre sí)
        if agrupar_por == "pais":
            stmt = (
                select(
                    Nacionalidad.id,
                    Nacionalidad.pais,
                    Nacionalidad.cod_pais,
                    ingresos_sum.label("cant_ingresos"),
                    perm_sum.label("cant_permanencias"),
                )
                .join(DetalleEstadisticaHotelera, Nacionalidad.id == DetalleEstadisticaHotelera.id_nacionalidad)
                .join(EstadisticaHotelera, DetalleEstadisticaHotelera.id_estadistica == EstadisticaHotelera.id)
                .where(EstadisticaHotelera.estado.in_(estados_validos))
                .group_by(Nacionalidad.id, Nacionalidad.pais, Nacionalidad.cod_pais)
                .order_by((ingresos_sum + perm_sum).desc())
            )

            # Filtros temporales
            if periodo.tipo_filtro == "rango_fechas":
                mes_case = cls._crear_mes_case_expression()
                fecha_num = EstadisticaHotelera.gestion * 10000 + mes_case * 100 + DetalleEstadisticaHotelera.dia
                f_ini_num = fecha_inicio.year * 10000 + fecha_inicio.month * 100 + fecha_inicio.day
                f_fin_num = fecha_fin.year * 10000 + fecha_fin.month * 100 + fecha_fin.day
                stmt = stmt.where(fecha_num >= f_ini_num, fecha_num <= f_fin_num)
            elif periodo.tipo_filtro == "mes_gestion":
                stmt = stmt.where(
                    func.lower(EstadisticaHotelera.mes) == periodo.mes,
                    EstadisticaHotelera.gestion == periodo.gestion,
                )
            elif periodo.tipo_filtro == "rango_gestiones":
                stmt = stmt.where(
                    EstadisticaHotelera.gestion >= periodo.gestion_inicio,
                    EstadisticaHotelera.gestion <= periodo.gestion_fin,
                )
            elif periodo.gestion:
                stmt = stmt.where(EstadisticaHotelera.gestion == periodo.gestion)

            if id_establecimiento:
                stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
            if categoria:
                stmt = stmt.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
                stmt = stmt.where(Establecimiento.categoria == categoria)

            if lista_ids:
                stmt = stmt.where(Nacionalidad.id.in_(lista_ids))
            if lista_cods:
                stmt = stmt.where(func.upper(Nacionalidad.cod_pais).in_(lista_cods))

            filas = (await db.execute(stmt)).all()

            for f in filas:
                ing = f.cant_ingresos
                perm = f.cant_permanencias
                tot = ing + perm
                ratio = round((perm / ing), 2) if ing > 0 else (1.0 if perm > 0 else 0.0)
                tot_ing += ing
                tot_perm += perm
                series.append(
                    SerieComparativaItem(
                        etiqueta=f.pais,
                        codigo=f.cod_pais,
                        id_nacionalidad=f.id,
                        ingresos=ing,
                        permanencias=perm,
                        total=tot,
                        ratio_permanencia_ingreso=ratio,
                    )
                )

        # MODO 2: AGRUPAR POR TIEMPO (Evolución cronológica de los países seleccionados)
        else:
            mes_case = cls._crear_mes_case_expression()

            # Si es por rango de fechas o un mes específico, agrupar por día
            if periodo.tipo_filtro in ["rango_fechas", "mes_gestion"]:
                stmt = (
                    select(
                        DetalleEstadisticaHotelera.dia.label("etiqueta_tiempo"),
                        ingresos_sum.label("cant_ingresos"),
                        perm_sum.label("cant_permanencias"),
                    )
                    .join(EstadisticaHotelera, DetalleEstadisticaHotelera.id_estadistica == EstadisticaHotelera.id)
                    .join(Nacionalidad, DetalleEstadisticaHotelera.id_nacionalidad == Nacionalidad.id)
                    .where(EstadisticaHotelera.estado.in_(estados_validos))
                    .group_by(DetalleEstadisticaHotelera.dia)
                    .order_by(DetalleEstadisticaHotelera.dia.asc())
                )

                if periodo.tipo_filtro == "rango_fechas":
                    fecha_num = EstadisticaHotelera.gestion * 10000 + mes_case * 100 + DetalleEstadisticaHotelera.dia
                    f_ini_num = fecha_inicio.year * 10000 + fecha_inicio.month * 100 + fecha_inicio.day
                    f_fin_num = fecha_fin.year * 10000 + fecha_fin.month * 100 + fecha_fin.day
                    stmt = stmt.where(fecha_num >= f_ini_num, fecha_num <= f_fin_num)
                else:
                    stmt = stmt.where(
                        func.lower(EstadisticaHotelera.mes) == periodo.mes,
                        EstadisticaHotelera.gestion == periodo.gestion,
                    )

                if id_establecimiento:
                    stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
                if categoria:
                    stmt = stmt.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
                    stmt = stmt.where(Establecimiento.categoria == categoria)

                if lista_ids:
                    stmt = stmt.where(Nacionalidad.id.in_(lista_ids))
                if lista_cods:
                    stmt = stmt.where(func.upper(Nacionalidad.cod_pais).in_(lista_cods))

                filas = (await db.execute(stmt)).all()

                for f in filas:
                    ing = f.cant_ingresos
                    perm = f.cant_permanencias
                    tot = ing + perm
                    ratio = round((perm / ing), 2) if ing > 0 else (1.0 if perm > 0 else 0.0)
                    tot_ing += ing
                    tot_perm += perm
                    series.append(
                        SerieComparativaItem(
                            etiqueta=f"Día {f.etiqueta_tiempo}",
                            ingresos=ing,
                            permanencias=perm,
                            total=tot,
                            ratio_permanencia_ingreso=ratio,
                        )
                    )

            # Si es por rango de gestiones o gestión completa, agrupar por mes
            else:
                stmt = (
                    select(
                        EstadisticaHotelera.gestion,
                        EstadisticaHotelera.mes,
                        mes_case.label("mes_num"),
                        ingresos_sum.label("cant_ingresos"),
                        perm_sum.label("cant_permanencias"),
                    )
                    .join(DetalleEstadisticaHotelera, DetalleEstadisticaHotelera.id_estadistica == EstadisticaHotelera.id)
                    .join(Nacionalidad, DetalleEstadisticaHotelera.id_nacionalidad == Nacionalidad.id)
                    .where(EstadisticaHotelera.estado.in_(estados_validos))
                    .group_by(EstadisticaHotelera.gestion, EstadisticaHotelera.mes, mes_case)
                    .order_by(EstadisticaHotelera.gestion.asc(), mes_case.asc())
                )

                if periodo.tipo_filtro == "rango_gestiones":
                    stmt = stmt.where(
                        EstadisticaHotelera.gestion >= periodo.gestion_inicio,
                        EstadisticaHotelera.gestion <= periodo.gestion_fin,
                    )
                elif periodo.gestion:
                    stmt = stmt.where(EstadisticaHotelera.gestion == periodo.gestion)

                if id_establecimiento:
                    stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
                if categoria:
                    stmt = stmt.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
                    stmt = stmt.where(Establecimiento.categoria == categoria)

                if lista_ids:
                    stmt = stmt.where(Nacionalidad.id.in_(lista_ids))
                if lista_cods:
                    stmt = stmt.where(func.upper(Nacionalidad.cod_pais).in_(lista_cods))

                filas = (await db.execute(stmt)).all()

                for f in filas:
                    ing = f.cant_ingresos
                    perm = f.cant_permanencias
                    tot = ing + perm
                    ratio = round((perm / ing), 2) if ing > 0 else (1.0 if perm > 0 else 0.0)
                    tot_ing += ing
                    tot_perm += perm
                    series.append(
                        SerieComparativaItem(
                            etiqueta=f"{f.mes.capitalize()} {f.gestion}",
                            ingresos=ing,
                            permanencias=perm,
                            total=tot,
                            ratio_permanencia_ingreso=ratio,
                        )
                    )

        promedio_gral = round((tot_perm / tot_ing), 2) if tot_ing > 0 else (1.0 if tot_perm > 0 else 0.0)

        filtro_paises_res = [str(x) for x in lista_ids] + list(lista_cods)

        return PermanenciasVsIngresosResponse(
            periodo=periodo,
            agrupacion=agrupar_por,
            filtro_paises_aplicado=filtro_paises_res if filtro_paises_res else None,
            series=series,
            totales=TotalesComparativa(
                total_ingresos=tot_ing,
                total_permanencias=tot_perm,
                promedio_general_noches=promedio_gral,
            ),
        )

    # ========================================================
    # 4. TABLERO EJECUTIVO Y KPIS DEPARTAMENTALES
    # ========================================================

    @classmethod
    async def obtener_tablero_ejecutivo(
        cls,
        db: AsyncSession,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        mes: str | None = None,
        gestion: int | None = None,
        gestion_inicio: int | None = None,
        gestion_fin: int | None = None,
        id_establecimiento: int | None = None,
        categoria: str | None = None,
    ) -> TableroEjecutivoResponse:
        """Calcula los indicadores institucionales consolidados y la tasa de ocupación departamental."""
        periodo = cls.normalizar_periodo(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            mes=mes,
            gestion=gestion,
            gestion_inicio=gestion_inicio,
            gestion_fin=gestion_fin,
        )

        estados_validos = [EstadoFormulario.ENVIADO, EstadoFormulario.APROBADO]

        # 1. Total establecimientos registrados
        stmt_est_activos = select(func.count(Establecimiento.id)).where(Establecimiento.activo.is_(True))
        if id_establecimiento:
            stmt_est_activos = stmt_est_activos.where(Establecimiento.id == id_establecimiento)
        if categoria:
            stmt_est_activos = stmt_est_activos.where(Establecimiento.categoria == categoria)
        tot_est_activos = (await db.execute(stmt_est_activos)).scalar_one() or 0

        # Capacidad de habitaciones instalada
        stmt_capacidad = select(func.coalesce(func.sum(Establecimiento.total_habitaciones), 0)).where(Establecimiento.activo.is_(True))
        if id_establecimiento:
            stmt_capacidad = stmt_capacidad.where(Establecimiento.id == id_establecimiento)
        if categoria:
            stmt_capacidad = stmt_capacidad.where(Establecimiento.categoria == categoria)
        capacidad_habitaciones = (await db.execute(stmt_capacidad)).scalar_one() or 0

        # 2. Formularios de EstadisticaHotelera
        stmt_est = (
            select(
                func.count(distinct(EstadisticaHotelera.id_establecimiento)),
                func.count(EstadisticaHotelera.id),
                func.coalesce(func.sum(EstadisticaHotelera.total_ing), 0),
                func.coalesce(func.sum(EstadisticaHotelera.total_perm), 0),
                func.coalesce(func.sum(EstadisticaHotelera.total), 0),
            )
            .where(EstadisticaHotelera.estado.in_(estados_validos))
        )

        if periodo.tipo_filtro == "mes_gestion":
            stmt_est = stmt_est.where(
                func.lower(EstadisticaHotelera.mes) == periodo.mes,
                EstadisticaHotelera.gestion == periodo.gestion,
            )
        elif periodo.tipo_filtro == "rango_gestiones":
            stmt_est = stmt_est.where(
                EstadisticaHotelera.gestion >= periodo.gestion_inicio,
                EstadisticaHotelera.gestion <= periodo.gestion_fin,
            )
        elif periodo.gestion:
            stmt_est = stmt_est.where(EstadisticaHotelera.gestion == periodo.gestion)

        if id_establecimiento:
            stmt_est = stmt_est.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
        if categoria:
            stmt_est = stmt_est.join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
            stmt_est = stmt_est.where(Establecimiento.categoria == categoria)

        res_est = (await db.execute(stmt_est)).one()
        est_declarantes, tot_forms, tot_ing, tot_perm, tot_huesp = res_est

        # 3. Ocupación hotelera
        stmt_ocup = (
            select(
                func.coalesce(func.sum(OcupacionHotelera.total_hab_ocupadas), 0)
            )
            .where(OcupacionHotelera.estado.in_(estados_validos))
        )

        if periodo.tipo_filtro == "mes_gestion":
            stmt_ocup = stmt_ocup.where(
                func.lower(OcupacionHotelera.mes) == periodo.mes,
                OcupacionHotelera.gestion == periodo.gestion,
            )
        elif periodo.tipo_filtro == "rango_gestiones":
            stmt_ocup = stmt_ocup.where(
                OcupacionHotelera.gestion >= periodo.gestion_inicio,
                OcupacionHotelera.gestion <= periodo.gestion_fin,
            )
        elif periodo.gestion:
            stmt_ocup = stmt_ocup.where(OcupacionHotelera.gestion == periodo.gestion)

        if id_establecimiento:
            stmt_ocup = stmt_ocup.where(OcupacionHotelera.id_establecimiento == id_establecimiento)
        if categoria:
            stmt_ocup = stmt_ocup.join(Establecimiento, OcupacionHotelera.id_establecimiento == Establecimiento.id)
            stmt_ocup = stmt_ocup.where(Establecimiento.categoria == categoria)

        tot_hab_ocupadas = (await db.execute(stmt_ocup)).scalar_one() or 0

        # Cálculo de días del período para la tasa de ocupación
        if periodo.tipo_filtro == "mes_gestion":
            mes_n = MESES_MAP.get(periodo.mes, 1)
            dias_periodo = calendar.monthrange(periodo.gestion, mes_n)[1]
        elif periodo.tipo_filtro == "rango_fechas":
            dias_periodo = max(1, (periodo.fecha_fin - periodo.fecha_inicio).days + 1)
        elif periodo.tipo_filtro == "rango_gestiones":
            dias_periodo = 365 * max(1, (periodo.gestion_fin - periodo.gestion_inicio + 1))
        else:
            dias_periodo = 365

        oferta_total_habitaciones_dias = capacidad_habitaciones * dias_periodo
        tasa_ocupacion = (
            round((tot_hab_ocupadas / oferta_total_habitaciones_dias * 100), 2)
            if oferta_total_habitaciones_dias > 0
            else 0.0
        )

        pct_cobertura = (
            round((est_declarantes / tot_est_activos * 100), 2)
            if tot_est_activos > 0
            else 0.0
        )

        estadia_media = (
            round((tot_perm / tot_ing), 2)
            if tot_ing > 0
            else (1.0 if tot_perm > 0 else 0.0)
        )

        return TableroEjecutivoResponse(
            periodo=periodo,
            establecimientos_registrados=tot_est_activos,
            establecimientos_declarantes=est_declarantes,
            porcentaje_cobertura_establecimientos=pct_cobertura,
            total_formularios_declarados=tot_forms,
            total_ingresos=tot_ing,
            total_permanencias=tot_perm,
            total_huespedes=tot_huesp,
            total_habitaciones_ofertadas=capacidad_habitaciones,
            total_habitaciones_ocupadas=tot_hab_ocupadas,
            tasa_ocupacion_porcentaje=tasa_ocupacion,
            estadia_media_noches=estadia_media,
        )

    # ========================================================
    # 5. BITÁCORA DE CUMPLIMIENTO INSTITUCIONAL
    # ========================================================

    @classmethod
    async def obtener_cumplimiento_declaraciones(
        cls,
        db: AsyncSession,
        mes: str,
        gestion: int,
    ) -> CumplimientoDeclaracionesResponse:
        """
        Verifica el estado de presentación mensual para cada establecimiento activo.
        Identifica cuáles han presentado ambos formularios y cuáles están en mora.
        """
        mes_clean = mes.strip().lower()
        if mes_clean not in MESES_MAP:
            raise BadRequestException(f"Mes no válido: '{mes}'.")

        # 1. Obtener todos los establecimientos activos
        stmt_est = (
            select(Establecimiento)
            .where(Establecimiento.activo.is_(True))
            .order_by(Establecimiento.nombre_establecimiento.asc())
        )
        establecimientos = (await db.execute(stmt_est)).scalars().all()

        # 2. Obtener formularios de estadísticas para el período
        stmt_forms_est = (
            select(EstadisticaHotelera)
            .where(
                func.lower(EstadisticaHotelera.mes) == mes_clean,
                EstadisticaHotelera.gestion == gestion,
            )
        )
        forms_est_res = (await db.execute(stmt_forms_est)).scalars().all()
        est_map = {f.id_establecimiento: f for f in forms_est_res}

        # 3. Obtener formularios de ocupación para el período
        stmt_forms_ocup = (
            select(OcupacionHotelera)
            .where(
                func.lower(OcupacionHotelera.mes) == mes_clean,
                OcupacionHotelera.gestion == gestion,
            )
        )
        forms_ocup_res = (await db.execute(stmt_forms_ocup)).scalars().all()
        ocup_map = {f.id_establecimiento: f for f in forms_ocup_res}

        items: list[EstablecimientoCumplimientoItem] = []
        al_dia_count = 0

        for est in establecimientos:
            form_est = est_map.get(est.id)
            form_ocup = ocup_map.get(est.id)

            tiene_est = form_est is not None
            tiene_ocup = form_ocup is not None
            cumplimiento_completo = tiene_est and tiene_ocup

            if cumplimiento_completo:
                al_dia_count += 1

            items.append(
                EstablecimientoCumplimientoItem(
                    id_establecimiento=est.id,
                    nombre_establecimiento=est.nombre_establecimiento,
                    categoria=est.categoria,
                    telefono=est.telefono,
                    tiene_estadistica=tiene_est,
                    id_estadistica=form_est.id if form_est else None,
                    estado_estadistica=form_est.estado.value if form_est else None,
                    tiene_ocupacion=tiene_ocup,
                    id_ocupacion=form_ocup.id if form_ocup else None,
                    estado_ocupacion=form_ocup.estado.value if form_ocup else None,
                    cumplimiento_completo=cumplimiento_completo,
                )
            )

        total_est = len(establecimientos)
        pendientes = total_est - al_dia_count
        pct = round((al_dia_count / total_est * 100), 2) if total_est > 0 else 0.0

        return CumplimientoDeclaracionesResponse(
            mes=mes_clean.capitalize(),
            gestion=gestion,
            total_establecimientos=total_est,
            total_al_dia=al_dia_count,
            total_pendientes=pendientes,
            porcentaje_cumplimiento=pct,
            establecimientos=items,
        )

    # ========================================================
    # 6. EXPORTACIÓN DE REPORTES A CSV TABULADO
    # ========================================================

    @classmethod
    async def exportar_reporte_movimientos_csv(
        cls,
        db: AsyncSession,
        mes: str | None = None,
        gestion: int | None = None,
        gestion_inicio: int | None = None,
        gestion_fin: int | None = None,
        id_establecimiento: int | None = None,
        categoria: str | None = None,
    ) -> str:
        """Exporta los movimientos de estadísticas a formato CSV compatible con UTF-8 Excel."""
        periodo = cls.normalizar_periodo(
            mes=mes,
            gestion=gestion,
            gestion_inicio=gestion_inicio,
            gestion_fin=gestion_fin,
        )

        estados_validos = [EstadoFormulario.ENVIADO, EstadoFormulario.APROBADO]

        stmt = (
            select(
                Establecimiento.nombre_establecimiento,
                Establecimiento.categoria,
                EstadisticaHotelera.gestion,
                EstadisticaHotelera.mes,
                Nacionalidad.pais,
                Nacionalidad.cod_pais,
                DetalleEstadisticaHotelera.dia,
                DetalleEstadisticaHotelera.cant_ingresos,
                DetalleEstadisticaHotelera.cant_permanencias,
                (DetalleEstadisticaHotelera.cant_ingresos + DetalleEstadisticaHotelera.cant_permanencias).label("total"),
            )
            .join(EstadisticaHotelera, DetalleEstadisticaHotelera.id_estadistica == EstadisticaHotelera.id)
            .join(Establecimiento, EstadisticaHotelera.id_establecimiento == Establecimiento.id)
            .join(Nacionalidad, DetalleEstadisticaHotelera.id_nacionalidad == Nacionalidad.id)
            .where(EstadisticaHotelera.estado.in_(estados_validos))
            .order_by(
                EstadisticaHotelera.gestion.desc(),
                EstadisticaHotelera.mes.asc(),
                Establecimiento.nombre_establecimiento.asc(),
                DetalleEstadisticaHotelera.dia.asc()
            )
        )

        if periodo.tipo_filtro == "mes_gestion":
            stmt = stmt.where(
                func.lower(EstadisticaHotelera.mes) == periodo.mes,
                EstadisticaHotelera.gestion == periodo.gestion,
            )
        elif periodo.tipo_filtro == "rango_gestiones":
            stmt = stmt.where(
                EstadisticaHotelera.gestion >= periodo.gestion_inicio,
                EstadisticaHotelera.gestion <= periodo.gestion_fin,
            )
        elif periodo.gestion:
            stmt = stmt.where(EstadisticaHotelera.gestion == periodo.gestion)

        if id_establecimiento:
            stmt = stmt.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)
        if categoria:
            stmt = stmt.where(Establecimiento.categoria == categoria)

        filas = (await db.execute(stmt)).all()

        output = io.StringIO()
        # BOM para compatibilidad con Microsoft Excel
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=";")

        writer.writerow([
            "Establecimiento",
            "Categoría",
            "Gestión",
            "Mes",
            "País",
            "Código ISO",
            "Día",
            "Llegadas (Ingresos)",
            "Pernoctaciones (Permanencias)",
            "Total Afluencia"
        ])

        for f in filas:
            writer.writerow([
                f.nombre_establecimiento,
                f.categoria,
                f.gestion,
                f.mes.capitalize(),
                f.pais,
                f.cod_pais,
                f.dia,
                f.cant_ingresos,
                f.cant_permanencias,
                f.total,
            ])

        return output.getvalue()
