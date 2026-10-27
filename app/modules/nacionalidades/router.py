from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.nacionalidades.schemas import (
    NacionalidadCreate,
    NacionalidadResponse,
    NacionalidadSeedSummary,
    NacionalidadUpdate,
)
from app.modules.nacionalidades.service import nacionalidad_service
from app.modules.usuarios.dependencies import (
    get_current_active_user,
    require_roles,
)
from app.modules.usuarios.models import RolUsuario, Usuario

router = APIRouter(prefix="/nacionalidades", tags=["Catálogo de Nacionalidades"])


@router.get(
    "/",
    response_model=list[NacionalidadResponse],
    summary="Listar nacionalidades con filtros y búsqueda",
)
async def listar_nacionalidades(
    skip: int = Query(0, ge=0, description="Número de registros a omitir para paginación"),
    limit: int = Query(200, ge=1, le=500, description="Cantidad máxima de registros a retornar"),
    search: str | None = Query(None, description="Término de búsqueda por nombre de país o código"),
    continente: str | None = Query(None, description="Filtrar por continente o región geográfica"),
    solo_activos: bool = Query(True, description="Filtrar solo nacionalidades activas"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """
    Retorna el catálogo de nacionalidades y países con opciones de búsqueda y paginación.
    Accesible para todos los usuarios autenticados (Administradores, Operadores y Dependientes).
    """
    return await nacionalidad_service.get_nacionalidades(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        continente=continente,
        solo_activos=solo_activos,
    )


@router.get(
    "/{id}",
    response_model=NacionalidadResponse,
    summary="Consultar nacionalidad por ID",
)
async def obtener_nacionalidad_por_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Obtiene el detalle completo de una nacionalidad específica a partir de su ID."""
    return await nacionalidad_service.get_by_id(db=db, id=id)


@router.get(
    "/codigo/{cod_pais}",
    response_model=NacionalidadResponse,
    summary="Consultar nacionalidad por código ISO o código especial",
)
async def obtener_nacionalidad_por_codigo(
    cod_pais: str,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Obtiene el registro de una nacionalidad mediante su código oficial (ej: 'BO', 'US', 'XAM')."""
    return await nacionalidad_service.get_by_codigo(db=db, cod_pais=cod_pais)


@router.post(
    "/",
    response_model=NacionalidadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva nacionalidad (Solo Administrador)",
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
)
async def crear_nacionalidad(
    data: NacionalidadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Permite al Administrador Departamental dar de alta una nueva nacionalidad o procedencia."""
    return await nacionalidad_service.create(db=db, data=data)


@router.patch(
    "/{id}",
    response_model=NacionalidadResponse,
    summary="Actualizar parcialmente una nacionalidad (Solo Administrador)",
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
)
async def actualizar_nacionalidad(
    id: int,
    data: NacionalidadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Permite al Administrador Departamental actualizar nombre, código o estado de una nacionalidad."""
    return await nacionalidad_service.update(db=db, id=id, data=data)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deshabilitar nacionalidad (Soft delete) (Solo Administrador)",
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
)
async def eliminar_nacionalidad(
    id: int,
    hard_delete: bool = Query(False, description="Si es True, elimina físicamente el registro"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Deshabilita lógicamente una nacionalidad para preservar integridad referencial estadística."""
    await nacionalidad_service.delete(db=db, id=id, deshabilitar_solo=not hard_delete)
    return None


@router.post(
    "/seed",
    response_model=NacionalidadSeedSummary,
    summary="Poblar catálogo con países oficiales y formulario departamental (Solo Administrador)",
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))],
)
async def poblar_catalogo_nacionalidades(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """
    Ejecuta el proceso de seeding idempotente con el catálogo oficial de países
    del formulario PDHO de Oruro y cobertura mundial.
    """
    return await nacionalidad_service.seed_catalogo_inicial(db=db)
