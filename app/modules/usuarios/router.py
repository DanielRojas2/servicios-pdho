from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.modules.usuarios.dependencies import (
    get_current_active_user,
    require_roles,
)
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.usuarios.schemas import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.modules.usuarios.service import usuario_service

router = APIRouter(prefix="/usuarios", tags=["Usuarios y Autenticación"])


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Inicio de sesión para Administradores y Operadores de Hospedaje.
    Genera y retorna un token JWT válido conforme a las políticas de seguridad.
    """
    usuario = await usuario_service.authenticate(
        db,
        email=login_data.email,
        password=login_data.password
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario inactivo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(usuario.id))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(usuario)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Usuario = Depends(get_current_active_user)
):
    """Retorna la información del perfil del usuario actualmente autenticado."""
    return current_user


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))]
)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Crea un nuevo usuario en la plataforma.
    Restringido al Administrador Departamental.
    Envía automáticamente las credenciales al correo del usuario y registra el estado en `credenciales_enviadas`.
    """
    existente = await usuario_service.get_by_email(db, user_in.email)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )

    nuevo_usuario = await usuario_service.create_user(db, user_in, send_email=True)
    return nuevo_usuario


@router.get(
    "/",
    response_model=list[UserResponse],
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))]
)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    rol: RolUsuario | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Lista usuarios registrados con paginación y filtro opcional por rol."""
    usuarios = await usuario_service.get_all(db, skip=skip, limit=limit, rol=rol)
    return usuarios


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene los detalles de un usuario por su identificador único."""
    # Solo el propio usuario o el administrador pueden ver los datos
    if current_user.rol != RolUsuario.ADMIN_DEPARTAMENTAL and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene autorización para ver los datos de este usuario."
        )

    usuario = await usuario_service.get_by_id(db, user_id=user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )
    return usuario


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))]
)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza la información de un usuario. Restringido a Administradores."""
    usuario = await usuario_service.get_by_id(db, user_id=user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    if user_in.email and user_in.email != usuario.email:
        existente = await usuario_service.get_by_email(db, user_in.email)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico especificado ya pertenece a otro usuario."
            )

    usuario_actualizado = await usuario_service.update_user(db, usuario, user_in)
    return usuario_actualizado


@router.post(
    "/{user_id}/reenviar-credenciales",
    dependencies=[Depends(require_roles(RolUsuario.ADMIN_DEPARTAMENTAL))]
)
async def resend_credentials(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Regenera una contraseña temporal y reenvía las credenciales al correo del usuario."""
    usuario = await usuario_service.get_by_id(db, user_id=user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    enviado = await usuario_service.resend_credentials(db, usuario)
    return {
        "mensaje": "Credenciales procesadas exitosamente." if enviado else "No se pudo entregar el correo con las credenciales.",
        "credenciales_enviadas": enviado,
        "email": usuario.email
    }
