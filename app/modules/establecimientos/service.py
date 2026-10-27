from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.email import send_user_credentials_email
from app.core.security import get_password_hash
from app.modules.establecimientos.models import (
    Establecimiento,
    Habitaciones,
    TipoHabitacion,
    TipoHabitacionEnum,
)
from app.modules.establecimientos.schemas import (
    CapacidadHabitacionesUpdate,
    DependienteCreate,
    DependienteUpdate,
    EstablecimientoCreateConOperador,
    EstablecimientoUpdate,
)
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.usuarios.service import generate_secure_password, usuario_service


class EstablecimientoService:
    @staticmethod
    async def inicializar_tipos_habitacion_predeterminados(db: AsyncSession) -> None:
        """Crea en la base de datos los tipos de habitación estándar si aún no existen."""
        result = await db.execute(select(TipoHabitacion))
        existentes = {th.tipo_habitacion for th in result.scalars().all()}

        tipos_base = [
            (TipoHabitacionEnum.SIMPLE, "Habitación para 1 persona (1 cama simple)"),
            (TipoHabitacionEnum.DOBLE, "Habitación para 2 personas (2 camas separadas)"),
            (TipoHabitacionEnum.MATRIMONIAL, "Habitación con 1 cama de dos plazas / matrimonial"),
            (TipoHabitacionEnum.TRIPLE, "Habitación para 3 personas"),
            (TipoHabitacionEnum.MULTIPLE, "Habitación para 4 o más personas"),
            (TipoHabitacionEnum.SUITE, "Habitación tipo suite con comodidades especiales"),
        ]

        nuevos = []
        for enum_val, desc in tipos_base:
            if enum_val not in existentes:
                nuevos.append(TipoHabitacion(tipo_habitacion=enum_val, descripcion=desc))

        if nuevos:
            db.add_all(nuevos)
            await db.commit()

    @staticmethod
    async def get_tipos_habitacion(db: AsyncSession) -> list[TipoHabitacion]:
        """Obtiene el catálogo completo de tipos de habitaciones."""
        await EstablecimientoService.inicializar_tipos_habitacion_predeterminados(db)
        result = await db.execute(select(TipoHabitacion).order_by(TipoHabitacion.id.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, establecimiento_id: int) -> Establecimiento | None:
        """Obtiene un establecimiento por ID con sus relaciones precargadas."""
        result = await db.execute(
            select(Establecimiento)
            .where(Establecimiento.id == establecimiento_id)
            .options(
                selectinload(Establecimiento.operador),
                selectinload(Establecimiento.habitaciones).joinedload(Habitaciones.tipo_habitacion)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_operador_id(db: AsyncSession, operador_id: int) -> Establecimiento | None:
        """Obtiene el establecimiento asociado directamente al operador titular o dependiente."""
        # Primero buscar por id_operador titular
        result = await db.execute(
            select(Establecimiento)
            .where(Establecimiento.id_operador == operador_id)
            .options(
                selectinload(Establecimiento.operador),
                selectinload(Establecimiento.habitaciones).joinedload(Habitaciones.tipo_habitacion)
            )
        )
        est = result.scalar_one_or_none()
        if est:
            return est

        # Si no es titular, buscar por usuario con id_establecimiento
        user = await usuario_service.get_by_id(db, operador_id)
        if user and user.id_establecimiento:
            return await EstablecimientoService.get_by_id(db, user.id_establecimiento)

        return None

    @staticmethod
    async def get_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        categoria: str | None = None,
        solo_activos: bool | None = None,
        buscar: str | None = None,
    ) -> list[Establecimiento]:
        """Lista establecimientos registrados con filtros opcionales."""
        query = (
            select(Establecimiento)
            .options(
                selectinload(Establecimiento.operador),
                selectinload(Establecimiento.habitaciones).joinedload(Habitaciones.tipo_habitacion)
            )
        )
        if categoria:
            query = query.where(Establecimiento.categoria == categoria)
        if solo_activos is not None:
            query = query.where(Establecimiento.activo == solo_activos)
        if buscar:
            query = query.where(Establecimiento.nombre_establecimiento.ilike(f"%{buscar.strip()}%"))

        query = query.offset(skip).limit(limit).order_by(Establecimiento.id.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def crear_establecimiento_con_operador(
        db: AsyncSession,
        data: EstablecimientoCreateConOperador,
        send_email: bool = True
    ) -> Establecimiento:
        """
        Crea un nuevo establecimiento y registra a su usuario operador/administrador inicial
        de forma atómica, enviándole sus credenciales automáticas por correo electrónico.
        """
        # Asegurar catálogo de tipos de habitación
        await EstablecimientoService.inicializar_tipos_habitacion_predeterminados(db)

        # 1. Crear el establecimiento inicialmente
        nuevo_est = Establecimiento(
            nombre_establecimiento=data.nombre_establecimiento.strip(),
            direccion=data.direccion.strip(),
            categoria=data.categoria.strip(),
            latitud=data.latitud,
            longitud=data.longitud,
            telefono=data.telefono.strip() if data.telefono else None,
            total_habitaciones=0,
            total_plazas=data.total_plazas,
            activo=True
        )
        db.add(nuevo_est)
        await db.flush()  # Genera nuevo_est.id

        # 2. Crear usuario operador asociado a este establecimiento
        plain_password = data.operador_password or generate_secure_password()
        hashed_pwd = get_password_hash(plain_password)
        normalized_email = data.operador_email.strip().lower()

        nuevo_operador = Usuario(
            email=normalized_email,
            nombre_completo=data.operador_nombre_completo.strip(),
            password_hash=hashed_pwd,
            rol=RolUsuario.OPERADOR_HOSPEDAJE,
            id_establecimiento=nuevo_est.id,
            activo=True,
            credenciales_enviadas=False
        )
        db.add(nuevo_operador)
        await db.flush()  # Genera nuevo_operador.id

        # 3. Vincular operador titular al establecimiento
        nuevo_est.id_operador = nuevo_operador.id

        # 4. Enviar credenciales por correo
        if send_email:
            enviado = await send_user_credentials_email(
                to_email=normalized_email,
                full_name=nuevo_operador.nombre_completo,
                plain_password=plain_password,
                role_name=nuevo_operador.rol.value
            )
            nuevo_operador.credenciales_enviadas = enviado

        await db.commit()
        await db.refresh(nuevo_est)
        return await EstablecimientoService.get_by_id(db, nuevo_est.id)  # type: ignore

    @staticmethod
    async def actualizar_establecimiento(
        db: AsyncSession,
        establecimiento: Establecimiento,
        data: EstablecimientoUpdate
    ) -> Establecimiento:
        """Actualiza la información técnica y de contacto de un establecimiento."""
        if data.nombre_establecimiento is not None:
            establecimiento.nombre_establecimiento = data.nombre_establecimiento.strip()
        if data.direccion is not None:
            establecimiento.direccion = data.direccion.strip()
        if data.categoria is not None:
            establecimiento.categoria = data.categoria.strip()
        if data.latitud is not None:
            establecimiento.latitud = data.latitud
        if data.longitud is not None:
            establecimiento.longitud = data.longitud
        if data.telefono is not None:
            establecimiento.telefono = data.telefono.strip()
        if data.total_plazas is not None:
            establecimiento.total_plazas = data.total_plazas
        if data.activo is not None:
            establecimiento.activo = data.activo

        await db.commit()
        await db.refresh(establecimiento)
        return await EstablecimientoService.get_by_id(db, establecimiento.id)  # type: ignore

    @staticmethod
    async def actualizar_capacidad(
        db: AsyncSession,
        establecimiento: Establecimiento,
        capacidad_in: CapacidadHabitacionesUpdate
    ) -> Establecimiento:
        """
        Actualiza el desglose de habitaciones por tipo y recalcula automáticamente
        el total_habitaciones según RN-2.
        """
        # Eliminar desglose anterior para este establecimiento
        await db.execute(
            delete(Habitaciones).where(Habitaciones.id_establecimiento == establecimiento.id)
        )

        total_habs = 0
        for item in capacidad_in.habitaciones:
            if item.cant_habitaciones > 0:
                hab = Habitaciones(
                    id_establecimiento=establecimiento.id,
                    id_tipo_habitacion=item.id_tipo_habitacion,
                    cant_habitaciones=item.cant_habitaciones,
                    nro_camas=item.nro_camas
                )
                db.add(hab)
                total_habs += item.cant_habitaciones

        # Actualizar total_habitaciones en el establecimiento (RN-2)
        establecimiento.total_habitaciones = total_habs

        await db.commit()
        await db.refresh(establecimiento)
        return await EstablecimientoService.get_by_id(db, establecimiento.id)  # type: ignore

    # -----------------------------------------------------------------------
    # Gestión de Dependientes del Establecimiento (Multi-tenant por establecimiento)
    # -----------------------------------------------------------------------

    @staticmethod
    async def get_dependientes(db: AsyncSession, establecimiento_id: int) -> list[Usuario]:
        """Retorna exclusivamente los dependientes pertenecientes a un establecimiento."""
        result = await db.execute(
            select(Usuario)
            .where(
                Usuario.id_establecimiento == establecimiento_id,
                Usuario.rol == RolUsuario.DEPENDIENTE_HOSPEDAJE
            )
            .order_by(Usuario.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def crear_dependiente(
        db: AsyncSession,
        establecimiento_id: int,
        dependiente_in: DependienteCreate,
        send_email: bool = True
    ) -> Usuario:
        """
        Crea un nuevo usuario con rol DEPENDIENTE_HOSPEDAJE vinculado
        única y exclusivamente al establecimiento del operador autenticado.
        """
        plain_password = dependiente_in.password or generate_secure_password()
        hashed_pwd = get_password_hash(plain_password)
        normalized_email = dependiente_in.email.strip().lower()

        nuevo_dep = Usuario(
            email=normalized_email,
            nombre_completo=dependiente_in.nombre_completo.strip(),
            password_hash=hashed_pwd,
            rol=RolUsuario.DEPENDIENTE_HOSPEDAJE,
            id_establecimiento=establecimiento_id,
            activo=True,
            credenciales_enviadas=False
        )
        db.add(nuevo_dep)
        await db.flush()

        if send_email:
            enviado = await send_user_credentials_email(
                to_email=normalized_email,
                full_name=nuevo_dep.nombre_completo,
                plain_password=plain_password,
                role_name=nuevo_dep.rol.value
            )
            nuevo_dep.credenciales_enviadas = enviado

        await db.commit()
        await db.refresh(nuevo_dep)
        return nuevo_dep

    @staticmethod
    async def actualizar_dependiente(
        db: AsyncSession,
        establecimiento_id: int,
        dependiente_id: int,
        dependiente_in: DependienteUpdate
    ) -> Usuario | None:
        """Actualiza un dependiente asegurando aislamiento por establecimiento."""
        result = await db.execute(
            select(Usuario).where(
                Usuario.id == dependiente_id,
                Usuario.id_establecimiento == establecimiento_id,
                Usuario.rol == RolUsuario.DEPENDIENTE_HOSPEDAJE
            )
        )
        dep = result.scalar_one_or_none()
        if not dep:
            return None

        if dependiente_in.nombre_completo is not None:
            dep.nombre_completo = dependiente_in.nombre_completo.strip()
        if dependiente_in.email is not None:
            dep.email = dependiente_in.email.strip().lower()
        if dependiente_in.activo is not None:
            dep.activo = dependiente_in.activo

        await db.commit()
        await db.refresh(dep)
        return dep


establecimiento_service = EstablecimientoService()
