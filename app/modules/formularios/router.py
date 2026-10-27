from typing import Annotated
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException
from app.modules.formularios.models import EstadoFormulario
from app.modules.formularios.schemas import (
    EstadisticaHoteleraCreate,
    EstadisticaHoteleraPreviewResponse,
    EstadisticaHoteleraResponse,
    EstadisticaHoteleraUpdate,
    OcupacionHoteleraCreate,
    OcupacionHoteleraPreviewResponse,
    OcupacionHoteleraResponse,
    OcupacionHoteleraUpdate,
    PeriodosDisponiblesResponse,
    RespaldoAdjuntoResponse,
)
from app.modules.formularios.service import FormularioService
from app.modules.usuarios.dependencies import get_current_user
from app.modules.usuarios.models import RolUsuario, Usuario

router = APIRouter(tags=["Formularios Hoteleros (Digitalización y Operativa)"])


# ========================================================
# ENDPOINTS GENERALES: CALENDARIO Y RESPALDO FOTO A PDF
# ========================================================

@router.get(
    "/formularios/periodos-disponibles",
    response_model=PeriodosDisponiblesResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener meses y días según calendario real y períodos permitidos"
)
async def obtener_periodos_disponibles(
    gestion: Annotated[int, Query(description="Año o gestión a consultar (ej: 2026, 2025)")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    tipo_formulario: Annotated[str, Query(description="'estadistica' u 'ocupacion'")] = "estadistica",
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (solo Admin)")] = None
):
    """
    Retorna la lista de los 12 meses para la gestión seleccionada con:
    - Cantidad real de días según calendario (considerando años bisiestos).
    - Estado 'declarado' (si el establecimiento ya cargó el formulario en ese período).
    - Estado 'permitido' (true solo si es un mes anterior a la fecha actual y no fue declarado aún).
    """
    return await FormularioService.obtener_periodos_disponibles(
        db=db,
        current_user=current_user,
        gestion=gestion,
        tipo_formulario=tipo_formulario,
        id_establecimiento_override=id_establecimiento
    )


@router.post(
    "/formularios/subir-respaldo",
    response_model=RespaldoAdjuntoResponse,
    status_code=status.HTTP_200_OK,
    summary="Subir fotografía de respaldo y convertir internamente a PDF"
)
async def subir_respaldo_general(
    file: Annotated[UploadFile, File(description="Foto o escaneo de la planilla física")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    tipo_formulario: Annotated[str, Query(description="Tipo: 'estadistica' u 'ocupacion'")] = "formulario",
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (solo Admin)")] = None
):
    """
    Guarda la fotografía original y genera internamente un PDF compacto optimizado para respaldo.
    Retorna las rutas para asociarlas a la creación o actualización manual del formulario.
    """
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise BadRequestException("Formato no compatible. Suba una imagen en formato JPG, PNG o WEBP.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise BadRequestException("El archivo subido está vacío.")

    foto_rel, pdf_rel = await FormularioService.subir_respaldo_general(
        db=db,
        current_user=current_user,
        file_bytes=file_bytes,
        filename=file.filename or "respaldo.jpg",
        tipo_formulario=tipo_formulario,
        id_establecimiento_override=id_establecimiento
    )
    return RespaldoAdjuntoResponse(archivo_foto=foto_rel, archivo_pdf=pdf_rel)


# ========================================================
# ENDPOINTS: ESTADÍSTICAS HOTELERAS
# ========================================================

@router.post(
    "/estadisticas-hoteleras/",
    response_model=EstadisticaHoteleraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear declaración de Estadísticas Hoteleras desde cero"
)
@router.post(
    "/estadisticas-hoteleras/confirmar",
    response_model=EstadisticaHoteleraResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
async def crear_estadistica_hotelera(
    payload: EstadisticaHoteleraCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (solo para Admin)")] = None
):
    """
    Crea la declaración de Estadísticas Hoteleras desde cero.
    El usuario elige la fecha/período, carga los huéspedes hospedados y opcionalmente adjunta el respaldo.
    Mapea automáticamente Secciones A y C, calcula las sumatorias del resumen y persiste en estado ENVIADO.
    """
    return await FormularioService.confirmar_estadistica_limpio(
        db=db,
        current_user=current_user,
        payload=payload,
        id_establecimiento_override=id_establecimiento
    )


@router.put(
    "/estadisticas-hoteleras/{id}",
    response_model=EstadisticaHoteleraResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar o editar declaración de Estadísticas Hoteleras"
)
async def actualizar_estadistica(
    id: int,
    payload: EstadisticaHoteleraUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)]
):
    """Permite al operador o dependiente modificar o corregir datos del formulario cargado."""
    return await FormularioService.actualizar_estadistica(
        db=db,
        current_user=current_user,
        estadistica_id=id,
        payload=payload
    )


@router.post(
    "/estadisticas-hoteleras/{id}/respaldo",
    response_model=EstadisticaHoteleraResponse,
    status_code=status.HTTP_200_OK,
    summary="Adjuntar fotografía de respaldo a una declaración existente y convertir a PDF"
)
async def adjuntar_respaldo_estadistica(
    id: int,
    file: Annotated[UploadFile, File(description="Foto del formulario físico de respaldo")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)]
):
    """Sube la foto física como respaldo documental para el formulario y genera internamente el PDF."""
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise BadRequestException("Formato no compatible. Suba una imagen JPG, PNG o WEBP.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise BadRequestException("El archivo subido está vacío.")

    return await FormularioService.adjuntar_respaldo_estadistica(
        db=db,
        current_user=current_user,
        estadistica_id=id,
        file_bytes=file_bytes,
        filename=file.filename or "formulario_respaldo.jpg"
    )


@router.get(
    "/estadisticas-hoteleras/",
    response_model=list[EstadisticaHoteleraResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar declaraciones de Estadísticas Hoteleras"
)
async def listar_estadisticas(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    mes: Annotated[str | None, Query()] = None,
    gestion: Annotated[int | None, Query()] = None,
    estado: Annotated[EstadoFormulario | None, Query()] = None,
    id_establecimiento: Annotated[int | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50
):
    """Listado paginado con filtros. Aislamiento multi-tenant por establecimiento."""
    return await FormularioService.listar_estadisticas(
        db=db,
        current_user=current_user,
        mes=mes,
        gestion=gestion,
        estado=estado,
        id_establecimiento=id_establecimiento,
        skip=skip,
        limit=limit
    )


@router.get(
    "/estadisticas-hoteleras/{id}",
    response_model=EstadisticaHoteleraResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de formulario de Estadísticas Hoteleras"
)
async def obtener_estadistica(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)]
):
    """Obtiene el formulario por ID incluyendo secciones A y C mapeadas y matriz de nacionalidades."""
    return await FormularioService.obtener_estadistica_por_id(
        db=db,
        current_user=current_user,
        estadistica_id=id
    )


@router.post(
    "/estadisticas-hoteleras/procesar-imagen",
    response_model=EstadisticaHoteleraPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Cargar foto del formulario de Estadísticas Hoteleras y extraer borrador (Opcional)"
)
async def procesar_imagen_estadistica(
    file: Annotated[UploadFile, File(description="Fotografía del formulario 'ESTADÍSTICAS HOTELERAS'")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (solo para Admin)")] = None
):
    """Endpoint opcional para previsualización."""
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise BadRequestException("Formato no compatible. Suba una imagen en formato JPG, PNG o WEBP.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise BadRequestException("El archivo subido está vacío.")

    return await FormularioService.procesar_imagen_estadistica(
        db=db,
        current_user=current_user,
        file_bytes=file_bytes,
        filename=file.filename or "formulario_estadistica.jpg",
        id_establecimiento_override=id_establecimiento
    )


# ========================================================
# ENDPOINTS: OCUPACIÓN HOTELERA
# ========================================================

@router.post(
    "/ocupacion-hotelera/",
    response_model=OcupacionHoteleraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear declaración de Ocupación Hotelera desde cero"
)
@router.post(
    "/ocupacion-hotelera/confirmar",
    response_model=OcupacionHoteleraResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
async def crear_ocupacion_hotelera(
    payload: OcupacionHoteleraCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (solo para Admin)")] = None
):
    """
    Crea la declaración de Ocupación Hotelera desde cero.
    El usuario elige la fecha/período y carga las habitaciones ocupadas y personas por noche.
    Valida contra la capacidad total del establecimiento y guarda en estado ENVIADO.
    """
    return await FormularioService.confirmar_ocupacion_limpio(
        db=db,
        current_user=current_user,
        payload=payload,
        id_establecimiento_override=id_establecimiento
    )


@router.put(
    "/ocupacion-hotelera/{id}",
    response_model=OcupacionHoteleraResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar o editar declaración de Ocupación Hotelera"
)
async def actualizar_ocupacion(
    id: int,
    payload: OcupacionHoteleraUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)]
):
    """Permite al operador o dependiente modificar o corregir datos de la ocupación hotelera."""
    return await FormularioService.actualizar_ocupacion(
        db=db,
        current_user=current_user,
        ocupacion_id=id,
        payload=payload
    )


@router.post(
    "/ocupacion-hotelera/{id}/respaldo",
    response_model=OcupacionHoteleraResponse,
    status_code=status.HTTP_200_OK,
    summary="Adjuntar fotografía de respaldo a la ocupación y convertir a PDF"
)
async def adjuntar_respaldo_ocupacion(
    id: int,
    file: Annotated[UploadFile, File(description="Foto del formulario físico de ocupación")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)]
):
    """Sube la foto física como respaldo documental para ocupación y genera internamente el PDF."""
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise BadRequestException("Formato no compatible. Suba una imagen JPG, PNG o WEBP.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise BadRequestException("El archivo subido está vacío.")

    return await FormularioService.adjuntar_respaldo_ocupacion(
        db=db,
        current_user=current_user,
        ocupacion_id=id,
        file_bytes=file_bytes,
        filename=file.filename or "ocupacion_respaldo.jpg"
    )


@router.get(
    "/ocupacion-hotelera/",
    response_model=list[OcupacionHoteleraResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar declaraciones de Ocupación Hotelera"
)
async def listar_ocupaciones(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    mes: Annotated[str | None, Query()] = None,
    gestion: Annotated[int | None, Query()] = None,
    estado: Annotated[EstadoFormulario | None, Query()] = None,
    id_establecimiento: Annotated[int | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50
):
    """Listado de declaraciones de ocupación con filtros."""
    return await FormularioService.listar_ocupaciones(
        db=db,
        current_user=current_user,
        mes=mes,
        gestion=gestion,
        estado=estado,
        id_establecimiento=id_establecimiento,
        skip=skip,
        limit=limit
    )


@router.get(
    "/ocupacion-hotelera/{id}",
    response_model=OcupacionHoteleraResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de formulario de Ocupación Hotelera"
)
async def obtener_ocupacion(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)]
):
    """Obtiene el formulario de ocupación por ID con sus registros diarios."""
    return await FormularioService.obtener_ocupacion_por_id(
        db=db,
        current_user=current_user,
        ocupacion_id=id
    )


@router.post(
    "/ocupacion-hotelera/procesar-imagen",
    response_model=OcupacionHoteleraPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Cargar foto del formulario de Ocupación Hotelera y extraer borrador (Opcional)"
)
async def procesar_imagen_ocupacion(
    file: Annotated[UploadFile, File(description="Fotografía del formulario 'OCUPACIÓN HOTELERA'")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Usuario, Depends(get_current_user)],
    id_establecimiento: Annotated[int | None, Query(description="ID de establecimiento (solo para Admin)")] = None
):
    """Endpoint opcional para previsualización."""
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise BadRequestException("Formato no compatible. Suba una imagen en formato JPG, PNG o WEBP.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise BadRequestException("El archivo subido está vacío.")

    return await FormularioService.procesar_imagen_ocupacion(
        db=db,
        current_user=current_user,
        file_bytes=file_bytes,
        filename=file.filename or "formulario_ocupacion.jpg",
        id_establecimiento_override=id_establecimiento
    )
