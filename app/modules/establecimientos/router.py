from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.establecimientos.models import Establecimiento
from app.modules.establecimientos.schemas import (
    CapacidadHabitacionesUpdate,
    DependienteCreate,
    DependienteUpdate,
    EstablecimientoCreateConOperador,
    EstablecimientoResponse,
    EstablecimientoUpdate,
    HabitacionResponse,
    TipoHabitacionResponse,
)
from app.modules.establecimientos.service import establecimiento_service
from app.modules.usuarios.dependencies import (
    get_current_active_user,
    require_roles,
)
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.usuarios.schemas import UserResponse
from app.modules.usuarios.service import usuario_service

router = APIRouter(prefix="/establecimientos", tags=["Establecimientos y Capacidad"])


def _formatear_respuesta_establecimiento(est: Establecimiento) -> dict:
    """Transforma el modelo ORM en un diccionario compatible con EstablecimientoResponse."""
    habs_formateadas = []
    for h in est.habitaciones:
        habs_formateadas.append(
            HabitacionResponse(
                id_tipo_habitacion=h.id_tipo_habitacion,
                tipo_habitacion=h.tipo_habitacion.tipo_habitacion.value if h.tipo_habitacion else "",
                cant_habitaciones=h.cant_habitaciones,
                nro_camas=h.nro_camas,
            )
        )

    return {
        "id": est.id,
        "nombre_establecimiento": est.nombre_establecimiento,
        "direccion": est.direccion,
        "categoria": est.categoria,
        "latitud": est.latitud,
        "longitud": est.longitud,
        "telefono": est.telefono,
        "total_habitaciones": est.total_habitaciones,
        "total_plazas": est.total_plazas,
        "id_operador": est.id_operador,
        "activo": est.activo,
        "fecha_registro": est.fecha_registro,
        "operador": UserResponse.model_validate(est.operador) if est.operador else None,
        "habitaciones": habs_formateadas,
    }


# ---------------------------------------------------------------------------
# Catálogo de Tipos de Habitación
# ---------------------------------------------------------------------------

@router.get(
    "/tipos-habitacion",
    response_model=list[TipoHabitacionResponse],
    summary="Listar tipos de habitación disponibles"
)
async def list_tipos_habitacion(
    db: AsyncSession = Depends(get_db),
    _: Usuario = Depends(get_current_active_user)
):
    """Retorna el catálogo estándar de tipos de habitación (suite, matrimonial, simple, etc.)."""
    tipos = await establecimiento_service.get_tipos_habitacion(db)
    return tipos


# ---------------------------------------------------------------------------
# Autogestión por Operador de Hospedaje y Dependientes
# ---------------------------------------------------------------------------

@router.get(
    "/mi-establecimiento",
    response_model=EstablecimientoResponse,
    summary="Obtener ficha técnica del establecimiento del usuario en sesión"
)
async def get_mi_establecimiento(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(
        require_roles(RolUsuario.OPERADOR_HOSPEDAJE, RolUsuario.DEPENDIENTE_HOSPEDAJE)
    )
):
    """Retorna la ficha técnica y capacidad del establecimiento al que pertenece el usuario."""
    est = await establecimiento_service.get_by_operador_id(db, current_user.id)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un establecimiento vinculado a su cuenta de usuario."
        )
    return _formatear_respuesta_establecimiento(est)


@router.patch(
    "/mi-establecimiento",
    response_model=EstablecimientoResponse,
    summary="Actualizar datos del establecimiento propio (contacto o plazas manuales)"
)
async def update_mi_establecimiento(
    data: EstablecimientoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(
        require_roles(RolUsuario.OPERADOR_HOSPEDAJE, RolUsuario.DEPENDIENTE_HOSPEDAJE)
    )
):
    """Permite al operador o dependiente actualizar datos de contacto y total_plazas manual."""
    est = await establecimiento_service.get_by_operador_id(db, current_user.id)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un establecimiento vinculado a su cuenta."
        )

    # Los operadores/dependientes no pueden alterar el nombre ni estado de alta administrativa
    data_limpia = data.model_copy()
    if current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL:
        data_limpia.activo = None

    actualizado = await establecimiento_service.actualizar_establecimiento(db, est, data_limpia)
    return _formatear_respuesta_establecimiento(actualizado)


@router.put(
    "/mi-establecimiento/capacidad",
    response_model=EstablecimientoResponse,
    summary="Configurar capacidad instalada por tipo de habitación"
)
async def update_capacidad_habitaciones(
    capacidad_in: CapacidadHabitacionesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.OPERADOR_HOSPEDAJE))
):
    """
    Configura el desglose de habitaciones por tipo (cant_habitaciones, nro_camas)
    y recalcula automáticamente total_habitaciones según RN-2.
    Restringido al OPERADOR_HOSPEDAJE del establecimiento.
    """
    est = await establecimiento_service.get_by_operador_id(db, current_user.id)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un establecimiento vinculado a su cuenta."
        )

    actualizado = await establecimiento_service.actualizar_capacidad(db, est, capacidad_in)
    return _formatear_respuesta_establecimiento(actualizado)


# ---------------------------------------------------------------------------
# Gestión de Dependientes (Exclusivo para OPERADOR_HOSPEDAJE)
# ---------------------------------------------------------------------------

@router.get(
    "/mi-establecimiento/dependientes",
    response_model=list[UserResponse],
    summary="Listar dependientes del propio establecimiento"
)
async def list_mis_dependientes(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.OPERADOR_HOSPEDAJE))
):
    """Lista exclusivamente los usuarios con rol DEPENDIENTE_HOSPEDAJE pertenecientes a su establecimiento."""
    if not current_user.id_establecimiento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El operador actual no tiene un establecimiento asignado."
        )

    dependientes = await establecimiento_service.get_dependientes(
        db, establecimiento_id=current_user.id_establecimiento
    )
    return dependientes


@router.post(
    "/mi-establecimiento/dependientes",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo dependiente en el establecimiento propio"
)
async def create_dependiente(
    dependiente_in: DependienteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.OPERADOR_HOSPEDAJE))
):
    """
    Crea un nuevo usuario dependiente (personal de apoyo para carga de formularios).
    Se asocia automáticamente al establecimiento del operador y se le envían credenciales por correo.
    """
    if not current_user.id_establecimiento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El operador actual no tiene un establecimiento asignado."
        )

    # Validar que el correo no esté ocupado
    existente = await usuario_service.get_by_email(db, dependiente_in.email)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )

    nuevo_dep = await establecimiento_service.crear_dependiente(
        db,
        establecimiento_id=current_user.id_establecimiento,
        dependiente_in=dependiente_in,
        send_email=True
    )
    return nuevo_dep


@router.patch(
    "/mi-establecimiento/dependientes/{dependiente_id}",
    response_model=UserResponse,
    summary="Actualizar o habilitar/deshabilitar dependiente propio"
)
async def update_dependiente(
    dependiente_id: int,
    dependiente_in: DependienteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.OPERADOR_HOSPEDAJE))
):
    """
    Permite al operador modificar el estado activo o datos de un dependiente de su propio establecimiento.
    Garantiza aislamiento: no permite modificar dependientes de otros establecimientos.
    """
    if not current_user.id_establecimiento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El operador actual no tiene un establecimiento asignado."
        )

    if dependiente_in.email:
        existente = await usuario_service.get_by_email(db, dependiente_in.email)
        if existente and existente.id != dependiente_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya se encuentra registrado por otro usuario."
            )

    actualizado = await establecimiento_service.actualizar_dependiente(
        db,
        establecimiento_id=current_user.id_establecimiento,
        dependiente_id=dependiente_id,
        dependiente_in=dependiente_in
    )
    if not actualizado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependiente no encontrado en su establecimiento."
        )

    return actualizado


# ---------------------------------------------------------------------------
# Gestión Administrativa de Establecimientos (ADMIN_DEPARTAMENTAL)
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=EstablecimientoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
    summary="Registrar establecimiento y su operador titular (Admin Departamental)"
)
async def create_establecimiento(
    data: EstablecimientoCreateConOperador,
    db: AsyncSession = Depends(get_db)
):
    """
    Registra un nuevo establecimiento de hospedaje junto con su usuario OPERADOR_HOSPEDAJE inicial.
    Envía de manera automática las credenciales al operador y vincula ambos registros.
    """
    # Verificar que el email del operador no esté registrado
    existente = await usuario_service.get_by_email(db, data.operador_email)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un usuario registrado con el correo '{data.operador_email}'."
        )

    nuevo_est = await establecimiento_service.crear_establecimiento_con_operador(
        db, data=data, send_email=True
    )
    return _formatear_respuesta_establecimiento(nuevo_est)


@router.get(
    "/",
    response_model=list[EstablecimientoResponse],
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
    summary="Listar todos los establecimientos departamentales"
)
async def list_establecimientos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    categoria: str | None = None,
    solo_activos: bool | None = None,
    buscar: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Retorna la lista consolidada de establecimientos con filtros por categoría y búsqueda."""
    establecimientos = await establecimiento_service.get_all(
        db, skip=skip, limit=limit, categoria=categoria, solo_activos=solo_activos, buscar=buscar
    )
    return [_formatear_respuesta_establecimiento(e) for e in establecimientos]


@router.get(
    "/{establecimiento_id}",
    response_model=EstablecimientoResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
    summary="Obtener detalle de un establecimiento por ID"
)
async def get_establecimiento_por_id(
    establecimiento_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene la información técnica detallada de un establecimiento."""
    est = await establecimiento_service.get_by_id(db, establecimiento_id)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establecimiento no encontrado."
        )
    return _formatear_respuesta_establecimiento(est)


@router.patch(
    "/{establecimiento_id}",
    response_model=EstablecimientoResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
    summary="Actualizar datos de un establecimiento por ID"
)
async def update_establecimiento_por_id(
    establecimiento_id: int,
    data: EstablecimientoUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza datos generales de un establecimiento existente."""
    est = await establecimiento_service.get_by_id(db, establecimiento_id)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establecimiento no encontrado."
        )

    actualizado = await establecimiento_service.actualizar_establecimiento(db, est, data)
    return _formatear_respuesta_establecimiento(actualizado)
