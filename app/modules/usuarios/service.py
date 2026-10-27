import secrets
import string
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_user_credentials_email
from app.core.security import get_password_hash, verify_password
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.usuarios.schemas import UserCreate, UserUpdate


def generate_secure_password(length: int = 12) -> str:
    """Genera una contraseña aleatoria robusta cumpliendo las reglas de AGETIC."""
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("@$!%*?&#/._-")
    
    remaining_chars = string.ascii_letters + string.digits + "@$!%*?&#/._-"
    rest = "".join(secrets.choice(remaining_chars) for _ in range(length - 4))
    
    # Mezclar caracteres para que no tengan un patrón fijo
    pwd_list = list(upper + lower + digit + special + rest)
    secrets.SystemRandom().shuffle(pwd_list)
    return "".join(pwd_list)


class UsuarioService:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Usuario | None:
        """Obtiene un usuario por su ID."""
        result = await db.execute(select(Usuario).where(Usuario.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Usuario | None:
        """Obtiene un usuario por su correo electrónico normalizado en minúsculas."""
        normalized_email = email.strip().lower()
        result = await db.execute(select(Usuario).where(Usuario.email == normalized_email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        rol: RolUsuario | None = None
    ) -> list[Usuario]:
        """Obtiene el listado paginado de usuarios con filtro opcional por rol."""
        query = select(Usuario)
        if rol:
            query = query.where(Usuario.rol == rol)
        query = query.offset(skip).limit(limit).order_by(Usuario.id.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create_user(
        db: AsyncSession,
        user_in: UserCreate,
        send_email: bool = True
    ) -> Usuario:
        """
        Crea un nuevo usuario en la base de datos y envía sus credenciales de acceso por correo.
        Registra el estado de entrega en el atributo credenciales_enviadas.
        """
        # Normalizar email
        normalized_email = user_in.email.strip().lower()
        
        # Determinar contraseña en texto plano
        plain_password = user_in.password or generate_secure_password()
        hashed_password = get_password_hash(plain_password)

        nuevo_usuario = Usuario(
            email=normalized_email,
            nombre_completo=user_in.nombre_completo.strip(),
            password_hash=hashed_password,
            rol=user_in.rol,
            id_establecimiento=user_in.id_establecimiento,
            activo=True,
            credenciales_enviadas=False
        )

        db.add(nuevo_usuario)
        await db.flush()  # Obtiene el ID generado

        # Enviar correo con credenciales si está solicitado
        if send_email:
            email_enviado = await send_user_credentials_email(
                to_email=normalized_email,
                full_name=nuevo_usuario.nombre_completo,
                plain_password=plain_password,
                role_name=nuevo_usuario.rol.value
            )
            nuevo_usuario.credenciales_enviadas = email_enviado

        await db.commit()
        await db.refresh(nuevo_usuario)
        return nuevo_usuario

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Usuario | None:
        """Autentica las credenciales de un usuario y actualiza su último acceso."""
        usuario = await UsuarioService.get_by_email(db, email)
        if not usuario:
            return None
        if not usuario.activo:
            return None
        if not verify_password(password, usuario.password_hash):
            return None

        # Actualizar fecha de último login
        usuario.ultimo_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(usuario)
        return usuario

    @staticmethod
    async def update_user(
        db: AsyncSession,
        db_user: Usuario,
        user_in: UserUpdate
    ) -> Usuario:
        """Actualiza los datos de un usuario."""
        if user_in.email is not None:
            db_user.email = user_in.email.strip().lower()
        if user_in.nombre_completo is not None:
            db_user.nombre_completo = user_in.nombre_completo.strip()
        if user_in.rol is not None:
            db_user.rol = user_in.rol
        if user_in.id_establecimiento is not None:
            db_user.id_establecimiento = user_in.id_establecimiento
        if user_in.activo is not None:
            db_user.activo = user_in.activo

        await db.commit()
        await db.refresh(db_user)
        return db_user

    @staticmethod
    async def resend_credentials(
        db: AsyncSession,
        db_user: Usuario
    ) -> bool:
        """
        Regenera una contraseña temporal segura y la reenvía al correo del usuario.
        """
        plain_password = generate_secure_password()
        db_user.password_hash = get_password_hash(plain_password)

        email_enviado = await send_user_credentials_email(
            to_email=db_user.email,
            full_name=db_user.nombre_completo,
            plain_password=plain_password,
            role_name=db_user.rol.value
        )
        db_user.credenciales_enviadas = email_enviado
        await db.commit()
        await db.refresh(db_user)
        return email_enviado


usuario_service = UsuarioService()
