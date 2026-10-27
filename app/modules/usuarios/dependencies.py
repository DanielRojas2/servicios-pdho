from collections.abc import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.usuarios.service import usuario_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/usuarios/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Usuario:
    """Extrae y valida el usuario actual desde el Bearer Token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación no válidas o expiradas.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    usuario = await usuario_service.get_by_id(db, user_id=user_id)
    if usuario is None:
        raise credentials_exception

    return usuario


async def get_current_active_user(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """Valida que el usuario autenticado se encuentre activo en el sistema."""
    if not current_user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta de usuario inactiva o deshabilitada.",
        )
    return current_user


def require_roles(*allowed_roles: RolUsuario | list[RolUsuario] | tuple[RolUsuario, ...]) -> Callable:
    """
    Fábrica de dependencias RBAC para restringir endpoints a roles autorizados.
    Alineado a lineamientos de seguridad AGETIC.
    Permite invocar tanto require_roles(Rol.A, Rol.B) como require_roles([Rol.A, Rol.B]).
    """
    roles_aplanados: set[RolUsuario] = set()
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            roles_aplanados.update(r)
        else:
            roles_aplanados.add(r)

    async def role_checker(
        current_user: Usuario = Depends(get_current_active_user),
    ) -> Usuario:
        if current_user.rol not in roles_aplanados:
            roles_str = [r.value if hasattr(r, "value") else str(r) for r in roles_aplanados]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere uno de los siguientes roles: {roles_str}",
            )
        return current_user

    return role_checker
