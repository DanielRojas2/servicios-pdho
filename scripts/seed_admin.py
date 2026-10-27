import asyncio
import os
import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.security import get_password_hash
from app.modules.usuarios.models import RolUsuario, Usuario
import app.modules.establecimientos.models  # noqa: F401


async def seed_superadmin():
    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD
    nombre = "Administrador Departamental Oruro"

    print(f"Verificando usuario inicial: {email}...")
    async with async_session_maker() as session:
        result = await session.execute(select(Usuario).where(Usuario.email == email))
        user = result.scalar_one_or_none()

        if user:
            print(f"El usuario {email} ya existe en la base de datos.")
            return

        nuevo_admin = Usuario(
            email=email,
            nombre_completo=nombre,
            password_hash=get_password_hash(password),
            rol=RolUsuario.ADMIN_DEPARTAMENTAL,
            activo=True,
            credenciales_enviadas=False,
        )
        session.add(nuevo_admin)
        await session.commit()
        print(f"Usuario Administrador creado exitosamente:")
        print(f"  Email: {email}")
        print(f"  Rol: {RolUsuario.ADMIN_DEPARTAMENTAL.value}")
        print("  Contraseña inicial: [PROTEGIDA - Configurada en ADMIN_PASSWORD]")


if __name__ == "__main__":
    asyncio.run(seed_superadmin())
