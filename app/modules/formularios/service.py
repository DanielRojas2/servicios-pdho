import calendar
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.establecimientos.models import Establecimiento
from app.modules.formularios.file_service import FileStorageService
from app.modules.formularios.models import (
    DetalleEstadisticaHotelera,
    DetalleOcupacionHotelera,
    EstadisticaHotelera,
    EstadoFormulario,
    OcupacionHotelera,
)
from app.modules.formularios.schemas import (
    DetalleEstadisticaInput,
    DetalleEstadisticaResponse,
    DetalleOcupacionInput,
    DetalleOcupacionResponse,
    EstadisticaHoteleraCreate,
    EstadisticaHoteleraPreviewResponse,
    EstadisticaHoteleraResponse,
    EstadisticaHoteleraUpdate,
    MesDisponibleResponse,
    OcupacionHoteleraCreate,
    OcupacionHoteleraPreviewResponse,
    OcupacionHoteleraResponse,
    OcupacionHoteleraUpdate,
    PeriodosDisponiblesResponse,
    ResumenEstadistica,
    SeccionAMapeada,
    SeccionCMapeada,
    TipoHabitacionMapeada,
)
from app.modules.nacionalidades.models import Nacionalidad
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.formularios.vision_service import VisionFormularioService

MESES_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

MESES_NOMBRES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


class FormularioService:
    """Lógica de negocio y persistencia atómica para los formularios PDHO."""

    # ========================================================
    # HELPERS DE MAPEO Y CÁLCULOS
    # ========================================================

    @staticmethod
    async def get_user_establecimiento(db: AsyncSession, current_user: Usuario) -> Establecimiento:
        """Obtiene el establecimiento asociado al usuario validando permisos multi-tenant."""
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL:
            # Si es admin, puede consultar sobre cualquier establecimiento especificado
            # pero por defecto si tiene uno asignado lo retorna
            if current_user.id_establecimiento:
                result = await db.execute(
                    select(Establecimiento)
                    .options(selectinload(Establecimiento.habitaciones))
                    .where(Establecimiento.id == current_user.id_establecimiento)
                )
                est = result.scalar_one_or_none()
                if est:
                    return est
            # Si es admin general sin establecimiento asociado, toma el primero registrado para contexto
            res_admin = await db.execute(
                select(Establecimiento).options(selectinload(Establecimiento.habitaciones))
            )
            est_first = res_admin.scalars().first()
            if not est_first:
                raise NotFoundException("No existen establecimientos registrados en la plataforma.")
            return est_first

        if not current_user.id_establecimiento:
            raise ForbiddenException("El usuario no tiene un establecimiento asignado.")

        result = await db.execute(
            select(Establecimiento)
            .options(selectinload(Establecimiento.habitaciones))
            .where(Establecimiento.id == current_user.id_establecimiento)
        )
        establecimiento = result.scalar_one_or_none()
        if not establecimiento:
            raise NotFoundException("Establecimiento asociado no encontrado.")
        return establecimiento

    @staticmethod
    def mapear_secciones(establecimiento: Establecimiento) -> tuple[SeccionAMapeada, SeccionCMapeada]:
        """Mapea las secciones A y C a partir de la ficha técnica y capacidad instalada."""
        seccion_a = SeccionAMapeada(
            nombre_establecimiento=establecimiento.nombre_establecimiento,
            direccion=establecimiento.direccion,
            categoria=establecimiento.categoria,
            ciudad="Oruro",
            telefono=establecimiento.telefono
        )

        habitaciones_list: list[TipoHabitacionMapeada] = []
        for hab in establecimiento.habitaciones:
            habitaciones_list.append(
                TipoHabitacionMapeada(
                    tipo_habitacion=hab.tipo_habitacion.tipo_habitacion.value,
                    cant_habitaciones=hab.cant_habitaciones,
                    nro_camas=hab.nro_camas
                )
            )

        seccion_c = SeccionCMapeada(
            habitaciones=habitaciones_list,
            total_habitaciones=establecimiento.total_habitaciones,
            total_plazas=establecimiento.total_plazas
        )
        return seccion_a, seccion_c

    @staticmethod
    def calcular_resumen(
        detalles: list[DetalleEstadisticaInput],
        id_bolivia: int
    ) -> ResumenEstadistica:
        """
        Calcula de forma automática y estricta el cuadro de resumen:
        Nacionales (Bolivia) vs Extranjeros (resto del mundo).
        """
        r_ing_nals = 0
        r_perm_nals = 0
        r_ing_extr = 0
        r_perm_extr = 0

        for d in detalles:
            if d.id_nacionalidad == id_bolivia:
                r_ing_nals += d.cant_ingresos
                r_perm_nals += d.cant_permanencias
            else:
                r_ing_extr += d.cant_ingresos
                r_perm_extr += d.cant_permanencias

        total_nals = r_ing_nals + r_perm_nals
        total_extr = r_ing_extr + r_perm_extr
        total_ing = r_ing_nals + r_ing_extr
        total_perm = r_perm_nals + r_perm_extr
        total_general = total_nals + total_extr

        return ResumenEstadistica(
            r_ingreso_nals=r_ing_nals,
            r_ingreso_extr=r_ing_extr,
            r_permanencia_nals=r_perm_nals,
            r_permanencia_extr=r_perm_extr,
            total_nals=total_nals,
            total_extr=total_extr,
            total_ing=total_ing,
            total_perm=total_perm,
            total=total_general
        )

    @staticmethod
    def validar_periodo_y_dias(
        mes: str,
        gestion: int,
        detalles: list,
        es_admin: bool = False
    ) -> int:
        """
        Valida que el mes y gestión correspondan a un período anterior al actual
        (o cualquier mes si la gestión es anterior) y que cada día registrado se encuentre
        dentro del número real de días del mes según calendario (considerando bisiestos).
        Retorna el número máximo real de días del mes.
        """
        mes_norm = mes.strip().lower()
        if mes_norm not in MESES_MAP:
            raise BadRequestException(
                f"El mes '{mes}' no es válido. Debe ser uno de los 12 meses del año en español."
            )

        mes_num = MESES_MAP[mes_norm]
        hoy = date.today()

        # Regla de períodos permitidos: meses anteriores al actual
        if not es_admin:
            if gestion > hoy.year:
                raise BadRequestException(
                    f"La gestión {gestion} es posterior a la gestión actual ({hoy.year}). "
                    f"Solo se permite declarar períodos pasados."
                )
            if gestion == hoy.year and mes_num >= hoy.month:
                mes_actual_nombre = MESES_NOMBRES[hoy.month - 1]
                raise BadRequestException(
                    f"No se puede declarar el período {mes.capitalize()} {gestion}. "
                    f"Para la gestión {hoy.year}, solo se pueden declarar meses concluidos anteriores a {mes_actual_nombre}."
                )

        dias_en_mes = calendar.monthrange(gestion, mes_num)[1]

        for d in detalles:
            if d.dia < 1 or d.dia > dias_en_mes:
                raise BadRequestException(
                    f"El día {d.dia} no es válido para {mes.capitalize()} de {gestion}. "
                    f"Este mes cuenta con un máximo real de {dias_en_mes} días según calendario."
                )

        return dias_en_mes

    # ========================================================
    # MÓDULO 1: ESTADÍSTICAS HOTELERAS
    # ========================================================

    @staticmethod
    async def procesar_imagen_estadistica(
        db: AsyncSession,
        current_user: Usuario,
        file_bytes: bytes,
        filename: str,
        id_establecimiento_override: int | None = None
    ) -> EstadisticaHoteleraPreviewResponse:
        """
        Pipeline no bloqueante:
        1. Almacena la imagen y genera internamente el PDF.
        2. Mapea Secciones A y C del establecimiento autenticado.
        3. Realiza reconocimiento inteligente de número en rojo, mes, año y matriz.
        4. Calcula el resumen y devuelve el borrador listo para edición humana en Angular.
        """
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL and id_establecimiento_override:
            res = await db.execute(
                select(Establecimiento)
                .options(selectinload(Establecimiento.habitaciones))
                .where(Establecimiento.id == id_establecimiento_override)
            )
            establecimiento = res.scalar_one_or_none()
            if not establecimiento:
                raise NotFoundException("Establecimiento indicado no encontrado.")
        else:
            establecimiento = await FormularioService.get_user_establecimiento(db, current_user)

        # Conversión segura y liviana a PDF
        foto_rel, pdf_rel = await FileStorageService.save_and_convert_to_pdf(
            file_bytes=file_bytes,
            filename=filename,
            establecimiento_id=establecimiento.id,
            tipo_formulario="estadistica"
        )

        # Mapa de códigos de país para asociar nacionalidades
        nac_res = await db.execute(select(Nacionalidad))
        nacionalidades = nac_res.scalars().all()
        nac_map = {n.cod_pais.upper(): n.id for n in nacionalidades}
        id_bolivia = nac_map.get("BO", 1)

        # Extracción inteligente
        datos_extraidos = await VisionFormularioService.extract_estadistica_from_image(
            image_bytes=file_bytes,
            filename=filename,
            nacionalidades_map=nac_map
        )

        seccion_a, seccion_c = FormularioService.mapear_secciones(establecimiento)
        matriz = datos_extraidos["matriz_detalles"]
        resumen = FormularioService.calcular_resumen(matriz, id_bolivia)

        return EstadisticaHoteleraPreviewResponse(
            numero_formulario=datos_extraidos["numero_formulario"],
            mes=datos_extraidos["mes"],
            gestion=datos_extraidos["gestion"],
            fecha_presentacion=datos_extraidos["fecha_presentacion"],
            cant_emp_perma=datos_extraidos["cant_emp_perma"],
            cant_emp_event=datos_extraidos["cant_emp_event"],
            total_empleados=datos_extraidos["cant_emp_perma"] + datos_extraidos["cant_emp_event"],
            archivo_foto=foto_rel,
            archivo_pdf=pdf_rel,
            seccion_a=seccion_a,
            seccion_c=seccion_c,
            matriz_detalles=matriz,
            resumen=resumen,
            advertencias=datos_extraidos["advertencias"]
        )

    @staticmethod
    async def confirmar_estadistica_limpio(
        db: AsyncSession,
        current_user: Usuario,
        payload: EstadisticaHoteleraCreate,
        id_establecimiento_override: int | None = None
    ) -> EstadisticaHoteleraResponse:
        """
        Guarda en limpio la declaración de Estadísticas Hoteleras.
        Acepta todas las modificaciones y correcciones hechas por el usuario en Angular.
        Aplica persistencia dispersa para las celdas con datos y validaciones matemáticas completas.
        """
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL and id_establecimiento_override:
            res = await db.execute(
                select(Establecimiento)
                .options(selectinload(Establecimiento.habitaciones))
                .where(Establecimiento.id == id_establecimiento_override)
            )
            establecimiento = res.scalar_one_or_none()
            if not establecimiento:
                raise NotFoundException("Establecimiento especificado no encontrado.")
        else:
            establecimiento = await FormularioService.get_user_establecimiento(db, current_user)

        # Validar período y días reales del mes según calendario
        FormularioService.validar_periodo_y_dias(
            mes=payload.mes,
            gestion=payload.gestion,
            detalles=payload.detalles,
            es_admin=(current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL)
        )

        # Verificar unicidad estricta para no duplicar formularios en el período
        existente_query = await db.execute(
            select(EstadisticaHotelera).where(
                EstadisticaHotelera.id_establecimiento == establecimiento.id,
                EstadisticaHotelera.mes.ilike(payload.mes.strip()),
                EstadisticaHotelera.gestion == payload.gestion
            )
        )
        existente = existente_query.scalar_one_or_none()
        if existente:
            raise ConflictException(
                f"El formulario de Estadísticas Hoteleras para el período {payload.mes} {payload.gestion} "
                f"ya fue registrado previamente para este establecimiento."
            )

        # Obtener ID de Bolivia para el cálculo del resumen
        bolivia_res = await db.execute(
            select(Nacionalidad).where(Nacionalidad.cod_pais == "BO")
        )
        nac_bolivia = bolivia_res.scalar_one_or_none()
        id_bolivia = nac_bolivia.id if nac_bolivia else 1

        # Filtrar solo celdas con datos > 0 (matriz dispersa)
        detalles_con_datos = [
            d for d in payload.detalles
            if (d.cant_ingresos > 0 or d.cant_permanencias > 0)
        ]

        # Recalcular automáticamente el resumen en base a los datos editados por el usuario
        resumen = FormularioService.calcular_resumen(detalles_con_datos, id_bolivia)

        nuevo_estado = (
            EstadoFormulario.ENVIADO if payload.enviar_en_limpio else EstadoFormulario.BORRADOR
        )

        total_emp = payload.cant_emp_perma + payload.cant_emp_event

        if existente:
            # Actualizar borrador previo
            existente.numero_formulario = payload.numero_formulario
            existente.fecha_presentacion = payload.fecha_presentacion
            existente.cant_emp_perma = payload.cant_emp_perma
            existente.cant_emp_event = payload.cant_emp_event
            existente.total_empleados = total_emp
            existente.archivo_foto = payload.archivo_foto or existente.archivo_foto
            existente.archivo_pdf = payload.archivo_pdf or existente.archivo_pdf
            existente.estado = nuevo_estado
            existente.observaciones = payload.observaciones

            existente.r_ingreso_nals = resumen.r_ingreso_nals
            existente.r_ingreso_extr = resumen.r_ingreso_extr
            existente.r_permanencia_nals = resumen.r_permanencia_nals
            existente.r_permanencia_extr = resumen.r_permanencia_extr
            existente.total_nals = resumen.total_nals
            existente.total_extr = resumen.total_extr
            existente.total_ing = resumen.total_ing
            existente.total_perm = resumen.total_perm
            existente.total = resumen.total

            # Limpiar detalles anteriores y recrear
            existente.detalles.clear()
            for d in detalles_con_datos:
                existente.detalles.append(
                    DetalleEstadisticaHotelera(
                        id_nacionalidad=d.id_nacionalidad,
                        dia=d.dia,
                        cant_ingresos=d.cant_ingresos,
                        cant_permanencias=d.cant_permanencias
                    )
                )
            formulario_obj = existente
        else:
            # Crear nueva declaración
            formulario_obj = EstadisticaHotelera(
                numero_formulario=payload.numero_formulario,
                id_establecimiento=establecimiento.id,
                mes=payload.mes,
                gestion=payload.gestion,
                fecha_presentacion=payload.fecha_presentacion,
                cant_emp_perma=payload.cant_emp_perma,
                cant_emp_event=payload.cant_emp_event,
                total_empleados=total_emp,
                archivo_foto=payload.archivo_foto,
                archivo_pdf=payload.archivo_pdf,
                estado=nuevo_estado,
                observaciones=payload.observaciones,
                r_ingreso_nals=resumen.r_ingreso_nals,
                r_ingreso_extr=resumen.r_ingreso_extr,
                r_permanencia_nals=resumen.r_permanencia_nals,
                r_permanencia_extr=resumen.r_permanencia_extr,
                total_nals=resumen.total_nals,
                total_extr=resumen.total_extr,
                total_ing=resumen.total_ing,
                total_perm=resumen.total_perm,
                total=resumen.total
            )
            for d in detalles_con_datos:
                formulario_obj.detalles.append(
                    DetalleEstadisticaHotelera(
                        id_nacionalidad=d.id_nacionalidad,
                        dia=d.dia,
                        cant_ingresos=d.cant_ingresos,
                        cant_permanencias=d.cant_permanencias
                    )
                )
            db.add(formulario_obj)

        await db.commit()
        await db.refresh(formulario_obj)

        seccion_a, seccion_c = FormularioService.mapear_secciones(establecimiento)
        resp = EstadisticaHoteleraResponse.model_validate(formulario_obj)
        resp.seccion_a = seccion_a
        resp.seccion_c = seccion_c
        
        # Enriquecer detalles con datos de país
        resp.detalles = [
            DetalleEstadisticaResponse(
                id=d.id,
                dia=d.dia,
                id_nacionalidad=d.id_nacionalidad,
                pais=d.nacionalidad.pais if d.nacionalidad else None,
                cod_pais=d.nacionalidad.cod_pais if d.nacionalidad else None,
                cant_ingresos=d.cant_ingresos,
                cant_permanencias=d.cant_permanencias
            )
            for d in formulario_obj.detalles
        ]
        return resp

    @staticmethod
    async def obtener_estadistica_por_id(
        db: AsyncSession,
        current_user: Usuario,
        estadistica_id: int
    ) -> EstadisticaHoteleraResponse:
        """Obtiene la declaración por ID con sus secciones mapeadas y detalles."""
        query = (
            select(EstadisticaHotelera)
            .options(
                selectinload(EstadisticaHotelera.detalles).joinedload(DetalleEstadisticaHotelera.nacionalidad),
                selectinload(EstadisticaHotelera.establecimiento).selectinload(Establecimiento.habitaciones)
            )
            .where(EstadisticaHotelera.id == estadistica_id)
        )
        res = await db.execute(query)
        obj = res.scalar_one_or_none()
        if not obj:
            raise NotFoundException("Formulario de Estadísticas Hoteleras no encontrado.")

        # Verificar permisos
        if (
            current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL
            and current_user.id_establecimiento != obj.id_establecimiento
        ):
            raise ForbiddenException("No tiene permisos para acceder a esta declaración.")

        seccion_a, seccion_c = FormularioService.mapear_secciones(obj.establecimiento)
        resp = EstadisticaHoteleraResponse.model_validate(obj)
        resp.seccion_a = seccion_a
        resp.seccion_c = seccion_c
        resp.detalles = [
            DetalleEstadisticaResponse(
                id=d.id,
                dia=d.dia,
                id_nacionalidad=d.id_nacionalidad,
                pais=d.nacionalidad.pais if d.nacionalidad else None,
                cod_pais=d.nacionalidad.cod_pais if d.nacionalidad else None,
                cant_ingresos=d.cant_ingresos,
                cant_permanencias=d.cant_permanencias
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def listar_estadisticas(
        db: AsyncSession,
        current_user: Usuario,
        mes: str | None = None,
        gestion: int | None = None,
        estado: EstadoFormulario | None = None,
        id_establecimiento: int | None = None,
        skip: int = 0,
        limit: int = 50
    ) -> list[EstadisticaHoteleraResponse]:
        """Listado de declaraciones con filtros y aislamiento multi-tenant."""
        query = (
            select(EstadisticaHotelera)
            .options(
                selectinload(EstadisticaHotelera.establecimiento).selectinload(Establecimiento.habitaciones),
                selectinload(EstadisticaHotelera.detalles).joinedload(DetalleEstadisticaHotelera.nacionalidad)
            )
        )

        if current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL:
            query = query.where(EstadisticaHotelera.id_establecimiento == current_user.id_establecimiento)
        elif id_establecimiento:
            query = query.where(EstadisticaHotelera.id_establecimiento == id_establecimiento)

        if mes:
            query = query.where(EstadisticaHotelera.mes.ilike(f"%{mes}%"))
        if gestion:
            query = query.where(EstadisticaHotelera.gestion == gestion)
        if estado:
            query = query.where(EstadisticaHotelera.estado == estado)

        query = query.order_by(EstadisticaHotelera.gestion.desc(), EstadisticaHotelera.id.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        items = res.scalars().all()

        resultado = []
        for obj in items:
            seccion_a, seccion_c = FormularioService.mapear_secciones(obj.establecimiento)
            resp = EstadisticaHoteleraResponse.model_validate(obj)
            resp.seccion_a = seccion_a
            resp.seccion_c = seccion_c
            resp.detalles = [
                DetalleEstadisticaResponse(
                    id=d.id,
                    dia=d.dia,
                    id_nacionalidad=d.id_nacionalidad,
                    pais=d.nacionalidad.pais if d.nacionalidad else None,
                    cod_pais=d.nacionalidad.cod_pais if d.nacionalidad else None,
                    cant_ingresos=d.cant_ingresos,
                    cant_permanencias=d.cant_permanencias
                )
                for d in obj.detalles
            ]
            resultado.append(resp)
        return resultado

    # ========================================================
    # MÓDULO 2: OCUPACIÓN HOTELERA
    # ========================================================

    @staticmethod
    async def procesar_imagen_ocupacion(
        db: AsyncSession,
        current_user: Usuario,
        file_bytes: bytes,
        filename: str,
        id_establecimiento_override: int | None = None
    ) -> OcupacionHoteleraPreviewResponse:
        """Pipeline de extracción para el formulario de Ocupación Hotelera."""
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL and id_establecimiento_override:
            res = await db.execute(
                select(Establecimiento).where(Establecimiento.id == id_establecimiento_override)
            )
            establecimiento = res.scalar_one_or_none()
            if not establecimiento:
                raise NotFoundException("Establecimiento indicado no encontrado.")
        else:
            establecimiento = await FormularioService.get_user_establecimiento(db, current_user)

        foto_rel, pdf_rel = await FileStorageService.save_and_convert_to_pdf(
            file_bytes=file_bytes,
            filename=filename,
            establecimiento_id=establecimiento.id,
            tipo_formulario="ocupacion"
        )

        datos = await VisionFormularioService.extract_ocupacion_from_image(file_bytes, filename)

        return OcupacionHoteleraPreviewResponse(
            mes=datos["mes"],
            gestion=datos["gestion"],
            fecha_presentacion=datos["fecha_presentacion"],
            total_hab_ocupadas=datos["total_hab_ocupadas"],
            total_personas=datos["total_personas"],
            archivo_foto=foto_rel,
            archivo_pdf=pdf_rel,
            detalles=datos["detalles"],
            advertencias=datos["advertencias"]
        )

    @staticmethod
    async def confirmar_ocupacion_limpio(
        db: AsyncSession,
        current_user: Usuario,
        payload: OcupacionHoteleraCreate,
        id_establecimiento_override: int | None = None
    ) -> OcupacionHoteleraResponse:
        """Guarda en limpio el formulario de Ocupación Hotelera."""
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL and id_establecimiento_override:
            res = await db.execute(
                select(Establecimiento).where(Establecimiento.id == id_establecimiento_override)
            )
            establecimiento = res.scalar_one_or_none()
            if not establecimiento:
                raise NotFoundException("Establecimiento especificado no encontrado.")
        else:
            establecimiento = await FormularioService.get_user_establecimiento(db, current_user)

        # Validar período y días reales del mes según calendario
        FormularioService.validar_periodo_y_dias(
            mes=payload.mes,
            gestion=payload.gestion,
            detalles=payload.detalles,
            es_admin=(current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL)
        )

        # Validar período existente para unicidad
        existente_res = await db.execute(
            select(OcupacionHotelera).where(
                OcupacionHotelera.id_establecimiento == establecimiento.id,
                OcupacionHotelera.mes.ilike(payload.mes.strip()),
                OcupacionHotelera.gestion == payload.gestion
            )
        )
        existente = existente_res.scalar_one_or_none()
        if existente:
            raise ConflictException(
                f"El formulario de Ocupación Hotelera para el período {payload.mes} {payload.gestion} "
                f"ya fue registrado previamente para este establecimiento."
            )

        # Validaciones de capacidad por día
        for det in payload.detalles:
            if det.hab_ocupadas > establecimiento.total_habitaciones:
                raise BadRequestException(
                    f"El día {det.dia} registra {det.hab_ocupadas} habitaciones ocupadas, "
                    f"lo cual supera la capacidad instalada total del establecimiento ({establecimiento.total_habitaciones})."
                )

        # Filtrar solo días con ocupación > 0
        detalles_con_datos = [
            d for d in payload.detalles if (d.hab_ocupadas > 0 or d.cant_personas > 0)
        ]

        total_habs = sum(d.hab_ocupadas for d in detalles_con_datos)
        total_pers = sum(d.cant_personas for d in detalles_con_datos)
        nuevo_estado = (
            EstadoFormulario.ENVIADO if payload.enviar_en_limpio else EstadoFormulario.BORRADOR
        )

        if existente:
            existente.fecha_presentacion = payload.fecha_presentacion
            existente.total_hab_ocupadas = total_habs
            existente.total_personas = total_pers
            existente.archivo_foto = payload.archivo_foto or existente.archivo_foto
            existente.archivo_pdf = payload.archivo_pdf or existente.archivo_pdf
            existente.estado = nuevo_estado
            existente.observaciones = payload.observaciones

            existente.detalles.clear()
            for d in detalles_con_datos:
                existente.detalles.append(
                    DetalleOcupacionHotelera(
                        dia=d.dia,
                        hab_ocupadas=d.hab_ocupadas,
                        cant_personas=d.cant_personas
                    )
                )
            obj = existente
        else:
            obj = OcupacionHotelera(
                id_establecimiento=establecimiento.id,
                mes=payload.mes,
                gestion=payload.gestion,
                fecha_presentacion=payload.fecha_presentacion,
                total_hab_ocupadas=total_habs,
                total_personas=total_pers,
                archivo_foto=payload.archivo_foto,
                archivo_pdf=payload.archivo_pdf,
                estado=nuevo_estado,
                observaciones=payload.observaciones
            )
            for d in detalles_con_datos:
                obj.detalles.append(
                    DetalleOcupacionHotelera(
                        dia=d.dia,
                        hab_ocupadas=d.hab_ocupadas,
                        cant_personas=d.cant_personas
                    )
                )
            db.add(obj)

        await db.commit()
        await db.refresh(obj)

        resp = OcupacionHoteleraResponse.model_validate(obj)
        resp.detalles = [
            DetalleOcupacionResponse(
                id=d.id,
                dia=d.dia,
                hab_ocupadas=d.hab_ocupadas,
                cant_personas=d.cant_personas
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def obtener_ocupacion_por_id(
        db: AsyncSession,
        current_user: Usuario,
        ocupacion_id: int
    ) -> OcupacionHoteleraResponse:
        """Obtiene la declaración de Ocupación por ID."""
        query = (
            select(OcupacionHotelera)
            .options(selectinload(OcupacionHotelera.detalles))
            .where(OcupacionHotelera.id == ocupacion_id)
        )
        res = await db.execute(query)
        obj = res.scalar_one_or_none()
        if not obj:
            raise NotFoundException("Formulario de Ocupación Hotelera no encontrado.")

        if (
            current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL
            and current_user.id_establecimiento != obj.id_establecimiento
        ):
            raise ForbiddenException("No tiene permisos para acceder a esta declaración.")

        resp = OcupacionHoteleraResponse.model_validate(obj)
        resp.detalles = [
            DetalleOcupacionResponse(
                id=d.id,
                dia=d.dia,
                hab_ocupadas=d.hab_ocupadas,
                cant_personas=d.cant_personas
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def listar_ocupaciones(
        db: AsyncSession,
        current_user: Usuario,
        mes: str | None = None,
        gestion: int | None = None,
        estado: EstadoFormulario | None = None,
        id_establecimiento: int | None = None,
        skip: int = 0,
        limit: int = 50
    ) -> list[OcupacionHoteleraResponse]:
        """Listado de formularios de ocupación con filtros."""
        query = select(OcupacionHotelera).options(selectinload(OcupacionHotelera.detalles))

        if current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL:
            query = query.where(OcupacionHotelera.id_establecimiento == current_user.id_establecimiento)
        elif id_establecimiento:
            query = query.where(OcupacionHotelera.id_establecimiento == id_establecimiento)

        if mes:
            query = query.where(OcupacionHotelera.mes.ilike(f"%{mes}%"))
        if gestion:
            query = query.where(OcupacionHotelera.gestion == gestion)
        if estado:
            query = query.where(OcupacionHotelera.estado == estado)

        query = query.order_by(OcupacionHotelera.gestion.desc(), OcupacionHotelera.id.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        items = res.scalars().all()

        resultado = []
        for obj in items:
            resp = OcupacionHoteleraResponse.model_validate(obj)
            resp.detalles = [
                DetalleOcupacionResponse(
                    id=d.id,
                    dia=d.dia,
                    hab_ocupadas=d.hab_ocupadas,
                    cant_personas=d.cant_personas
                )
                for d in obj.detalles
            ]
            resultado.append(resp)
        return resultado

    @staticmethod
    async def actualizar_estadistica(
        db: AsyncSession,
        current_user: Usuario,
        estadistica_id: int,
        payload: EstadisticaHoteleraUpdate
    ) -> EstadisticaHoteleraResponse:
        """Permite editar y actualizar una declaración de Estadísticas Hoteleras."""
        query = (
            select(EstadisticaHotelera)
            .options(
                selectinload(EstadisticaHotelera.detalles).joinedload(DetalleEstadisticaHotelera.nacionalidad),
                selectinload(EstadisticaHotelera.establecimiento).selectinload(Establecimiento.habitaciones)
            )
            .where(EstadisticaHotelera.id == estadistica_id)
        )
        res = await db.execute(query)
        obj = res.scalar_one_or_none()
        if not obj:
            raise NotFoundException("Formulario de Estadísticas Hoteleras no encontrado.")

        if (
            current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL
            and current_user.id_establecimiento != obj.id_establecimiento
        ):
            raise ForbiddenException("No tiene permisos para modificar este formulario.")

        if payload.numero_formulario is not None:
            obj.numero_formulario = payload.numero_formulario
        if payload.mes is not None:
            obj.mes = payload.mes
        if payload.gestion is not None:
            obj.gestion = payload.gestion
        if payload.fecha_presentacion is not None:
            obj.fecha_presentacion = payload.fecha_presentacion
        if payload.cant_emp_perma is not None:
            obj.cant_emp_perma = payload.cant_emp_perma
        if payload.cant_emp_event is not None:
            obj.cant_emp_event = payload.cant_emp_event
        obj.total_empleados = obj.cant_emp_perma + obj.cant_emp_event

        if payload.archivo_foto is not None:
            obj.archivo_foto = payload.archivo_foto
        if payload.archivo_pdf is not None:
            obj.archivo_pdf = payload.archivo_pdf
        if payload.observaciones is not None:
            obj.observaciones = payload.observaciones
        if payload.estado is not None:
            obj.estado = payload.estado

        # Si se envían nuevos detalles de huéspedes
        if payload.detalles is not None:
            bolivia_res = await db.execute(select(Nacionalidad).where(Nacionalidad.cod_pais == "BO"))
            nac_bolivia = bolivia_res.scalar_one_or_none()
            id_bolivia = nac_bolivia.id if nac_bolivia else 1

            detalles_con_datos = [
                d for d in payload.detalles if (d.cant_ingresos > 0 or d.cant_permanencias > 0)
            ]
            resumen = FormularioService.calcular_resumen(detalles_con_datos, id_bolivia)

            obj.r_ingreso_nals = resumen.r_ingreso_nals
            obj.r_ingreso_extr = resumen.r_ingreso_extr
            obj.r_permanencia_nals = resumen.r_permanencia_nals
            obj.r_permanencia_extr = resumen.r_permanencia_extr
            obj.total_nals = resumen.total_nals
            obj.total_extr = resumen.total_extr
            obj.total_ing = resumen.total_ing
            obj.total_perm = resumen.total_perm
            obj.total = resumen.total

            obj.detalles.clear()
            for d in detalles_con_datos:
                obj.detalles.append(
                    DetalleEstadisticaHotelera(
                        id_nacionalidad=d.id_nacionalidad,
                        dia=d.dia,
                        cant_ingresos=d.cant_ingresos,
                        cant_permanencias=d.cant_permanencias
                    )
                )

        await db.commit()
        await db.refresh(obj)

        seccion_a, seccion_c = FormularioService.mapear_secciones(obj.establecimiento)
        resp = EstadisticaHoteleraResponse.model_validate(obj)
        resp.seccion_a = seccion_a
        resp.seccion_c = seccion_c
        resp.detalles = [
            DetalleEstadisticaResponse(
                id=d.id,
                dia=d.dia,
                id_nacionalidad=d.id_nacionalidad,
                pais=d.nacionalidad.pais if d.nacionalidad else None,
                cod_pais=d.nacionalidad.cod_pais if d.nacionalidad else None,
                cant_ingresos=d.cant_ingresos,
                cant_permanencias=d.cant_permanencias
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def adjuntar_respaldo_estadistica(
        db: AsyncSession,
        current_user: Usuario,
        estadistica_id: int,
        file_bytes: bytes,
        filename: str
    ) -> EstadisticaHoteleraResponse:
        """Sube la imagen de respaldo, la transforma a PDF y la asocia a una declaración existente."""
        query = (
            select(EstadisticaHotelera)
            .options(
                selectinload(EstadisticaHotelera.detalles).joinedload(DetalleEstadisticaHotelera.nacionalidad),
                selectinload(EstadisticaHotelera.establecimiento).selectinload(Establecimiento.habitaciones)
            )
            .where(EstadisticaHotelera.id == estadistica_id)
        )
        res = await db.execute(query)
        obj = res.scalar_one_or_none()
        if not obj:
            raise NotFoundException("Formulario de Estadísticas Hoteleras no encontrado.")

        if (
            current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL
            and current_user.id_establecimiento != obj.id_establecimiento
        ):
            raise ForbiddenException("No tiene permisos para adjuntar respaldo a este formulario.")

        foto_rel, pdf_rel = await FileStorageService.save_and_convert_to_pdf(
            file_bytes=file_bytes,
            filename=filename,
            establecimiento_id=obj.id_establecimiento,
            tipo_formulario="estadistica"
        )
        obj.archivo_foto = foto_rel
        obj.archivo_pdf = pdf_rel
        await db.commit()
        await db.refresh(obj)

        seccion_a, seccion_c = FormularioService.mapear_secciones(obj.establecimiento)
        resp = EstadisticaHoteleraResponse.model_validate(obj)
        resp.seccion_a = seccion_a
        resp.seccion_c = seccion_c
        resp.detalles = [
            DetalleEstadisticaResponse(
                id=d.id,
                dia=d.dia,
                id_nacionalidad=d.id_nacionalidad,
                pais=d.nacionalidad.pais if d.nacionalidad else None,
                cod_pais=d.nacionalidad.cod_pais if d.nacionalidad else None,
                cant_ingresos=d.cant_ingresos,
                cant_permanencias=d.cant_permanencias
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def actualizar_ocupacion(
        db: AsyncSession,
        current_user: Usuario,
        ocupacion_id: int,
        payload: OcupacionHoteleraUpdate
    ) -> OcupacionHoteleraResponse:
        """Edita y actualiza un formulario de Ocupación Hotelera."""
        query = (
            select(OcupacionHotelera)
            .options(
                selectinload(OcupacionHotelera.detalles),
                selectinload(OcupacionHotelera.establecimiento)
            )
            .where(OcupacionHotelera.id == ocupacion_id)
        )
        res = await db.execute(query)
        obj = res.scalar_one_or_none()
        if not obj:
            raise NotFoundException("Formulario de Ocupación Hotelera no encontrado.")

        if (
            current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL
            and current_user.id_establecimiento != obj.id_establecimiento
        ):
            raise ForbiddenException("No tiene permisos para modificar este formulario.")

        if payload.mes is not None:
            obj.mes = payload.mes
        if payload.gestion is not None:
            obj.gestion = payload.gestion
        if payload.fecha_presentacion is not None:
            obj.fecha_presentacion = payload.fecha_presentacion
        if payload.archivo_foto is not None:
            obj.archivo_foto = payload.archivo_foto
        if payload.archivo_pdf is not None:
            obj.archivo_pdf = payload.archivo_pdf
        if payload.observaciones is not None:
            obj.observaciones = payload.observaciones
        if payload.estado is not None:
            obj.estado = payload.estado

        if payload.detalles is not None:
            for det in payload.detalles:
                if det.hab_ocupadas > obj.establecimiento.total_habitaciones:
                    raise BadRequestException(
                        f"El día {det.dia} registra {det.hab_ocupadas} habitaciones ocupadas, "
                        f"lo cual supera la capacidad instalada total ({obj.establecimiento.total_habitaciones})."
                    )

            detalles_con_datos = [
                d for d in payload.detalles if (d.hab_ocupadas > 0 or d.cant_personas > 0)
            ]
            obj.total_hab_ocupadas = sum(d.hab_ocupadas for d in detalles_con_datos)
            obj.total_personas = sum(d.cant_personas for d in detalles_con_datos)

            obj.detalles.clear()
            for d in detalles_con_datos:
                obj.detalles.append(
                    DetalleOcupacionHotelera(
                        dia=d.dia,
                        hab_ocupadas=d.hab_ocupadas,
                        cant_personas=d.cant_personas
                    )
                )

        await db.commit()
        await db.refresh(obj)

        resp = OcupacionHoteleraResponse.model_validate(obj)
        resp.detalles = [
            DetalleOcupacionResponse(
                id=d.id,
                dia=d.dia,
                hab_ocupadas=d.hab_ocupadas,
                cant_personas=d.cant_personas
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def adjuntar_respaldo_ocupacion(
        db: AsyncSession,
        current_user: Usuario,
        ocupacion_id: int,
        file_bytes: bytes,
        filename: str
    ) -> OcupacionHoteleraResponse:
        """Sube la foto de respaldo, genera el PDF y la asocia a una declaración de ocupación existente."""
        query = (
            select(OcupacionHotelera)
            .options(selectinload(OcupacionHotelera.detalles))
            .where(OcupacionHotelera.id == ocupacion_id)
        )
        res = await db.execute(query)
        obj = res.scalar_one_or_none()
        if not obj:
            raise NotFoundException("Formulario de Ocupación Hotelera no encontrado.")

        if (
            current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL
            and current_user.id_establecimiento != obj.id_establecimiento
        ):
            raise ForbiddenException("No tiene permisos para adjuntar respaldo a este formulario.")

        foto_rel, pdf_rel = await FileStorageService.save_and_convert_to_pdf(
            file_bytes=file_bytes,
            filename=filename,
            establecimiento_id=obj.id_establecimiento,
            tipo_formulario="ocupacion"
        )
        obj.archivo_foto = foto_rel
        obj.archivo_pdf = pdf_rel
        await db.commit()
        await db.refresh(obj)

        resp = OcupacionHoteleraResponse.model_validate(obj)
        resp.detalles = [
            DetalleOcupacionResponse(
                id=d.id,
                dia=d.dia,
                hab_ocupadas=d.hab_ocupadas,
                cant_personas=d.cant_personas
            )
            for d in obj.detalles
        ]
        return resp

    @staticmethod
    async def subir_respaldo_general(
        db: AsyncSession,
        current_user: Usuario,
        file_bytes: bytes,
        filename: str,
        tipo_formulario: str = "respaldo",
        id_establecimiento_override: int | None = None
    ) -> tuple[str, str]:
        """Sube una foto de respaldo y genera internamente el PDF correspondiente."""
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL and id_establecimiento_override:
            res = await db.execute(
                select(Establecimiento).where(Establecimiento.id == id_establecimiento_override)
            )
            est = res.scalar_one_or_none()
            if not est:
                raise NotFoundException("Establecimiento no encontrado.")
            est_id = est.id
        else:
            est = await FormularioService.get_user_establecimiento(db, current_user)
            est_id = est.id

        return await FileStorageService.save_and_convert_to_pdf(
            file_bytes=file_bytes,
            filename=filename,
            establecimiento_id=est_id,
            tipo_formulario=tipo_formulario
        )

    @staticmethod
    async def obtener_periodos_disponibles(
        db: AsyncSession,
        current_user: Usuario,
        gestion: int,
        tipo_formulario: str = "estadistica",
        id_establecimiento_override: int | None = None
    ) -> PeriodosDisponiblesResponse:
        """
        Calcula dinámicamente según calendario real qué meses están permitidos
        para declarar y cuáles ya fueron declarados previamente por el establecimiento.
        """
        if current_user.rol == RolUsuario.ADMIN_DEPARTAMENTAL and id_establecimiento_override:
            est_id = id_establecimiento_override
        else:
            est = await FormularioService.get_user_establecimiento(db, current_user)
            est_id = est.id

        hoy = date.today()

        if tipo_formulario.lower() == "ocupacion":
            query = select(OcupacionHotelera.mes, OcupacionHotelera.id).where(
                OcupacionHotelera.id_establecimiento == est_id,
                OcupacionHotelera.gestion == gestion
            )
        else:
            query = select(EstadisticaHotelera.mes, EstadisticaHotelera.id).where(
                EstadisticaHotelera.id_establecimiento == est_id,
                EstadisticaHotelera.gestion == gestion
            )

        res = await db.execute(query)
        declarados_map = {row[0].strip().capitalize(): row[1] for row in res.all()}

        meses_result = []
        for i, nombre_mes in enumerate(MESES_NOMBRES, start=1):
            dias_en_mes = calendar.monthrange(gestion, i)[1]
            ya_declarado = nombre_mes in declarados_map
            form_id = declarados_map.get(nombre_mes)

            if gestion < hoy.year:
                permitido = not ya_declarado
            elif gestion == hoy.year:
                permitido = (i < hoy.month) and not ya_declarado
            else:
                permitido = False

            meses_result.append(
                MesDisponibleResponse(
                    mes=nombre_mes,
                    numero_mes=i,
                    dias_en_mes=dias_en_mes,
                    declarado=ya_declarado,
                    permitido=permitido,
                    formulario_id=form_id
                )
            )

        return PeriodosDisponiblesResponse(gestion=gestion, meses=meses_result)
