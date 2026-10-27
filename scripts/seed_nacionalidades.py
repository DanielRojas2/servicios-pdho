import asyncio
import sys
from pathlib import Path

# Agregar directorio raíz al path para importación de módulos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import async_session_maker
import app.modules.usuarios.models  # noqa: F401
import app.modules.establecimientos.models  # noqa: F401
import app.modules.nacionalidades.models  # noqa: F401
from app.modules.nacionalidades.service import nacionalidad_service


async def seed_nacionalidades():
    """Ejecuta el poblamiento idempotente de nacionalidades en la base de datos."""
    print("Iniciando proceso de poblamiento (seeding) de Nacionalidades...")
    async with async_session_maker() as session:
        resumen = await nacionalidad_service.seed_catalogo_inicial(session)
        print("\nResultado del poblamiento de Nacionalidades:")
        print(f"  - Registros procesados en catálogo semilla: {resumen['total_registros_procesados']}")
        print(f"  - Nuevos registros insertados: {resumen['nuevos_insertados']}")
        print(f"  - Registros preexistentes omitidos: {resumen['existentes_omitidos']}")
        print(f"  - Total final de nacionalidades en base de datos: {resumen['total_catalogo']}\n")


if __name__ == "__main__":
    asyncio.run(seed_nacionalidades())
