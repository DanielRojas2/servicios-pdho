from collections.abc import Sequence
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.nacionalidades.models import Nacionalidad
from app.modules.nacionalidades.schemas import (
    NacionalidadCreate,
    NacionalidadUpdate,
)

# Catálogo oficial para el seed guiado en la planilla física de Oruro y cobertura mundial
PAISES_OFICIALES_SEED: list[dict[str, str]] = [
    # --- Columnas del Formulario Físico Departamental PDHO (Orden y opciones oficiales) ---
    {"pais": "Bolivia", "cod_pais": "BO", "continente": "América del Sur"},
    {"pais": "Argentina", "cod_pais": "AR", "continente": "América del Sur"},
    {"pais": "Brasil", "cod_pais": "BR", "continente": "América del Sur"},
    {"pais": "Colombia", "cod_pais": "CO", "continente": "América del Sur"},
    {"pais": "Chile", "cod_pais": "CL", "continente": "América del Sur"},
    {"pais": "Ecuador", "cod_pais": "EC", "continente": "América del Sur"},
    {"pais": "Paraguay", "cod_pais": "PY", "continente": "América del Sur"},
    {"pais": "Perú", "cod_pais": "PE", "continente": "América del Sur"},
    {"pais": "Uruguay", "cod_pais": "UY", "continente": "América del Sur"},
    {"pais": "Venezuela", "cod_pais": "VE", "continente": "América del Sur"},
    {"pais": "México", "cod_pais": "MX", "continente": "América del Norte"},
    {"pais": "Otros America", "cod_pais": "XAM", "continente": "América"},
    {"pais": "Canadá", "cod_pais": "CA", "continente": "América del Norte"},
    {"pais": "EE.UU.", "cod_pais": "US", "continente": "América del Norte"},
    {"pais": "Alemania", "cod_pais": "DE", "continente": "Europa"},
    {"pais": "España", "cod_pais": "ES", "continente": "Europa"},
    {"pais": "Francia", "cod_pais": "FR", "continente": "Europa"},
    {"pais": "Inglaterra", "cod_pais": "GB", "continente": "Europa"},
    {"pais": "Italia", "cod_pais": "IT", "continente": "Europa"},
    {"pais": "Suiza", "cod_pais": "CH", "continente": "Europa"},
    {"pais": "Holanda", "cod_pais": "NL", "continente": "Europa"},
    {"pais": "Suecia", "cod_pais": "SE", "continente": "Europa"},
    {"pais": "Otros Europa", "cod_pais": "XEU", "continente": "Europa"},
    {"pais": "Japón", "cod_pais": "JP", "continente": "Asia"},
    {"pais": "Israel", "cod_pais": "IL", "continente": "Asia"},
    {"pais": "Otros Asia", "cod_pais": "XAS", "continente": "Asia"},
    {"pais": "Oceanía", "cod_pais": "XOC", "continente": "Oceanía"},
    {"pais": "Otros", "cod_pais": "XX", "continente": "Otros"},

    # --- Cobertura de América (Central, Caribe y adicionales) ---
    {"pais": "Costa Rica", "cod_pais": "CR", "continente": "América Central"},
    {"pais": "Cuba", "cod_pais": "CU", "continente": "Caribe"},
    {"pais": "Panamá", "cod_pais": "PA", "continente": "América Central"},
    {"pais": "República Dominicana", "cod_pais": "DO", "continente": "Caribe"},
    {"pais": "Guatemala", "cod_pais": "GT", "continente": "América Central"},
    {"pais": "El Salvador", "cod_pais": "SV", "continente": "América Central"},
    {"pais": "Honduras", "cod_pais": "HN", "continente": "América Central"},
    {"pais": "Nicaragua", "cod_pais": "NI", "continente": "América Central"},
    {"pais": "Puerto Rico", "cod_pais": "PR", "continente": "Caribe"},
    {"pais": "Jamaica", "cod_pais": "JM", "continente": "Caribe"},
    {"pais": "Haití", "cod_pais": "HT", "continente": "Caribe"},
    {"pais": "Guyana", "cod_pais": "GY", "continente": "América del Sur"},
    {"pais": "Surinam", "cod_pais": "SR", "continente": "América del Sur"},

    # --- Cobertura de Europa (Adicionales más comunes) ---
    {"pais": "Portugal", "cod_pais": "PT", "continente": "Europa"},
    {"pais": "Bélgica", "cod_pais": "BE", "continente": "Europa"},
    {"pais": "Austria", "cod_pais": "AT", "continente": "Europa"},
    {"pais": "Noruega", "cod_pais": "NO", "continente": "Europa"},
    {"pais": "Dinamarca", "cod_pais": "DK", "continente": "Europa"},
    {"pais": "Finlandia", "cod_pais": "FI", "continente": "Europa"},
    {"pais": "Irlanda", "cod_pais": "IE", "continente": "Europa"},
    {"pais": "Polonia", "cod_pais": "PL", "continente": "Europa"},
    {"pais": "República Checa", "cod_pais": "CZ", "continente": "Europa"},
    {"pais": "Grecia", "cod_pais": "GR", "continente": "Europa"},
    {"pais": "Rusia", "cod_pais": "RU", "continente": "Europa"},
    {"pais": "Ucrania", "cod_pais": "UA", "continente": "Europa"},
    {"pais": "Rumania", "cod_pais": "RO", "continente": "Europa"},
    {"pais": "Croacia", "cod_pais": "HR", "continente": "Europa"},
    {"pais": "Hungría", "cod_pais": "HU", "continente": "Europa"},
    {"pais": "Turquía", "cod_pais": "TR", "continente": "Europa"},

    # --- Cobertura de Asia (Adicionales más comunes) ---
    {"pais": "China", "cod_pais": "CN", "continente": "Asia"},
    {"pais": "Corea del Sur", "cod_pais": "KR", "continente": "Asia"},
    {"pais": "India", "cod_pais": "IN", "continente": "Asia"},
    {"pais": "Taiwán", "cod_pais": "TW", "continente": "Asia"},
    {"pais": "Singapur", "cod_pais": "SG", "continente": "Asia"},
    {"pais": "Tailandia", "cod_pais": "TH", "continente": "Asia"},
    {"pais": "Vietnam", "cod_pais": "VN", "continente": "Asia"},
    {"pais": "Malasia", "cod_pais": "MY", "continente": "Asia"},
    {"pais": "Indonesia", "cod_pais": "ID", "continente": "Asia"},
    {"pais": "Filipinas", "cod_pais": "PH", "continente": "Asia"},
    {"pais": "Emiratos Árabes Unidos", "cod_pais": "AE", "continente": "Asia"},
    {"pais": "Arabia Saudita", "cod_pais": "SA", "continente": "Asia"},
    {"pais": "Qatar", "cod_pais": "QA", "continente": "Asia"},

    # --- Cobertura de Oceanía (Países más comunes) ---
    {"pais": "Australia", "cod_pais": "AU", "continente": "Oceanía"},
    {"pais": "Nueva Zelanda", "cod_pais": "NZ", "continente": "Oceanía"},
    {"pais": "Fiyi", "cod_pais": "FJ", "continente": "Oceanía"},
    {"pais": "Papúa Nueva Guinea", "cod_pais": "PG", "continente": "Oceanía"},

    # --- Cobertura de África (Países más comunes) ---
    {"pais": "Sudáfrica", "cod_pais": "ZA", "continente": "África"},
    {"pais": "Egipto", "cod_pais": "EG", "continente": "África"},
    {"pais": "Marruecos", "cod_pais": "MA", "continente": "África"},
    {"pais": "Nigeria", "cod_pais": "NG", "continente": "África"},
    {"pais": "Kenia", "cod_pais": "KE", "continente": "África"},
    {"pais": "Senegal", "cod_pais": "SN", "continente": "África"},
    {"pais": "Ghana", "cod_pais": "GH", "continente": "África"},
    {"pais": "Túnez", "cod_pais": "TN", "continente": "África"},
    {"pais": "Argelia", "cod_pais": "DZ", "continente": "África"},
    {"pais": "Etiopía", "cod_pais": "ET", "continente": "África"},
]


class NacionalidadService:
    """Servicio de lógica de negocio para administración y consulta de nacionalidades."""

    async def get_nacionalidades(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 200,
        search: str | None = None,
        continente: str | None = None,
        solo_activos: bool = True,
    ) -> Sequence[Nacionalidad]:
        """Recupera la lista de nacionalidades con soporte para paginación y filtros dinámicos."""
        query = select(Nacionalidad)

        if solo_activos:
            query = query.where(Nacionalidad.activo.is_(True))

        if continente:
            query = query.where(func.lower(Nacionalidad.continente) == continente.strip().lower())

        if search:
            filtro_busqueda = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Nacionalidad.pais.ilike(filtro_busqueda),
                    Nacionalidad.cod_pais.ilike(filtro_busqueda),
                )
            )

        query = query.order_by(Nacionalidad.pais.asc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def count_nacionalidades(
        self,
        db: AsyncSession,
        search: str | None = None,
        continente: str | None = None,
        solo_activos: bool = True,
    ) -> int:
        """Calcula el total de registros que satisfacen los filtros aplicados."""
        query = select(func.count(Nacionalidad.id))

        if solo_activos:
            query = query.where(Nacionalidad.activo.is_(True))

        if continente:
            query = query.where(func.lower(Nacionalidad.continente) == continente.strip().lower())

        if search:
            filtro_busqueda = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Nacionalidad.pais.ilike(filtro_busqueda),
                    Nacionalidad.cod_pais.ilike(filtro_busqueda),
                )
            )

        result = await db.execute(query)
        return result.scalar_one()

    async def get_by_id(self, db: AsyncSession, id: int) -> Nacionalidad:
        """Obtiene una nacionalidad por su ID o eleva un error 404."""
        result = await db.execute(select(Nacionalidad).where(Nacionalidad.id == id))
        nacionalidad = result.scalar_one_or_none()
        if not nacionalidad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La nacionalidad con ID {id} no fue encontrada.",
            )
        return nacionalidad

    async def get_by_codigo(self, db: AsyncSession, cod_pais: str) -> Nacionalidad:
        """Obtiene una nacionalidad por su código o eleva un error 404."""
        cod_normalizado = cod_pais.strip().upper()
        result = await db.execute(
            select(Nacionalidad).where(Nacionalidad.cod_pais == cod_normalizado)
        )
        nacionalidad = result.scalar_one_or_none()
        if not nacionalidad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró ninguna nacionalidad con el código '{cod_normalizado}'.",
            )
        return nacionalidad

    async def create(self, db: AsyncSession, data: NacionalidadCreate) -> Nacionalidad:
        """Crea una nueva nacionalidad validando unicidad de nombre y código."""
        # Verificar código duplicado
        res_cod = await db.execute(
            select(Nacionalidad).where(Nacionalidad.cod_pais == data.cod_pais)
        )
        if res_cod.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una nacionalidad registrada con el código '{data.cod_pais}'.",
            )

        # Verificar nombre de país duplicado
        res_pais = await db.execute(
            select(Nacionalidad).where(func.lower(Nacionalidad.pais) == data.pais.lower())
        )
        if res_pais.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una nacionalidad registrada con el nombre '{data.pais}'.",
            )

        nueva_nacionalidad = Nacionalidad(
            pais=data.pais,
            cod_pais=data.cod_pais,
            continente=data.continente,
            activo=data.activo,
        )
        db.add(nueva_nacionalidad)
        await db.commit()
        await db.refresh(nueva_nacionalidad)
        return nueva_nacionalidad

    async def update(
        self, db: AsyncSession, id: int, data: NacionalidadUpdate
    ) -> Nacionalidad:
        """Actualiza parcialmente los campos de una nacionalidad."""
        nacionalidad = await self.get_by_id(db, id)

        if data.cod_pais is not None and data.cod_pais != nacionalidad.cod_pais:
            res_cod = await db.execute(
                select(Nacionalidad).where(
                    Nacionalidad.cod_pais == data.cod_pais,
                    Nacionalidad.id != id,
                )
            )
            if res_cod.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El código '{data.cod_pais}' ya se encuentra asignado a otra nacionalidad.",
                )
            nacionalidad.cod_pais = data.cod_pais

        if data.pais is not None and data.pais.lower() != nacionalidad.pais.lower():
            res_pais = await db.execute(
                select(Nacionalidad).where(
                    func.lower(Nacionalidad.pais) == data.pais.lower(),
                    Nacionalidad.id != id,
                )
            )
            if res_pais.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El nombre '{data.pais}' ya se encuentra asignado a otra nacionalidad.",
                )
            nacionalidad.pais = data.pais

        if data.continente is not None:
            nacionalidad.continente = data.continente

        if data.activo is not None:
            nacionalidad.activo = data.activo

        await db.commit()
        await db.refresh(nacionalidad)
        return nacionalidad

    async def delete(self, db: AsyncSession, id: int, deshabilitar_solo: bool = True) -> None:
        """Deshabilita (soft delete) o elimina físicamente una nacionalidad."""
        nacionalidad = await self.get_by_id(db, id)
        if deshabilitar_solo:
            nacionalidad.activo = False
            await db.commit()
        else:
            await db.delete(nacionalidad)
            await db.commit()

    async def seed_catalogo_inicial(self, db: AsyncSession) -> dict[str, int]:
        """
        Puebla de manera idempotente el catálogo con los países del formulario oficial y cobertura mundial.
        No sobrescribe registros existentes, solo inserta los faltantes.
        """
        # Obtener códigos existentes
        result = await db.execute(select(Nacionalidad.cod_pais))
        codigos_existentes = set(result.scalars().all())

        nuevos_insertados = 0
        existentes_omitidos = 0

        for item in PAISES_OFICIALES_SEED:
            cod = item["cod_pais"].upper()
            if cod in codigos_existentes:
                existentes_omitidos += 1
                continue

            nueva = Nacionalidad(
                pais=item["pais"],
                cod_pais=cod,
                continente=item.get("continente"),
                activo=True,
            )
            db.add(nueva)
            codigos_existentes.add(cod)
            nuevos_insertados += 1

        if nuevos_insertados > 0:
            await db.commit()

        # Conteo final
        total_catalogo = await self.count_nacionalidades(db, solo_activos=False)

        return {
            "total_registros_procesados": len(PAISES_OFICIALES_SEED),
            "nuevos_insertados": nuevos_insertados,
            "existentes_omitidos": existentes_omitidos,
            "total_catalogo": total_catalogo,
        }


nacionalidad_service = NacionalidadService()
