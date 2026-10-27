from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.usuarios.models import RolUsuario
from app.modules.usuarios.schemas import UserCreate
from app.modules.usuarios.service import usuario_service


@pytest.mark.asyncio
async def test_crear_y_autenticar_usuario(client: AsyncClient, db_session: AsyncSession):
    """Verifica el flujo completo de creación de usuario, login y consulta de perfil (/me)."""
    # 1. Crear usuario administrador directamente en la sesión de pruebas
    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        admin = await usuario_service.create_user(
            db_session,
            UserCreate(
                email="admin@oruro.gob.bo",
                nombre_completo="Administrador Departamental",
                rol=RolUsuario.ADMIN_DEPARTAMENTAL,
                password="PasswordSeguro123!"
            ),
            send_email=True
        )
        assert admin.id is not None
        assert admin.credenciales_enviadas is True
        mock_email.assert_called_once()

    # 2. Login con credenciales válidas
    login_res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": "admin@oruro.gob.bo", "password": "PasswordSeguro123!"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["user"]["email"] == "admin@oruro.gob.bo"
    assert token_data["user"]["rol"] == RolUsuario.ADMIN_DEPARTAMENTAL.value
    assert token_data["user"]["credenciales_enviadas"] is True

    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Consultar perfil /me
    me_res = await client.get(f"{settings.API_V1_STR}/usuarios/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "admin@oruro.gob.bo"


@pytest.mark.asyncio
async def test_login_credenciales_invalidas(client: AsyncClient):
    """Verifica que el endpoint de login rechace credenciales incorrectas con 401."""
    res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": "noexiste@hotel.com", "password": "Password123!"}
    )
    assert res.status_code == 401
    assert "Credenciales incorrectas" in res.json()["detail"]


@pytest.mark.asyncio
async def test_control_de_acceso_rbac_operador_vs_admin(client: AsyncClient, db_session: AsyncSession):
    """Verifica que un operador no pueda crear nuevos usuarios (403 Forbidden)."""
    # Crear operador
    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        operador = await usuario_service.create_user(
            db_session,
            UserCreate(
                email="operador@hotel.com",
                nombre_completo="Operador Hotel",
                rol=RolUsuario.OPERADOR_HOSPEDAJE,
                password="PasswordSeguro123!"
            )
        )

    # Login operador
    login_res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": "operador@hotel.com", "password": "PasswordSeguro123!"}
    )
    operador_token = login_res.json()["access_token"]
    operador_headers = {"Authorization": f"Bearer {operador_token}"}

    # Intentar crear un usuario usando el token del operador
    create_res = await client.post(
        f"{settings.API_V1_STR}/usuarios/",
        headers=operador_headers,
        json={
            "email": "nuevo@hotel.com",
            "nombre_completo": "Nuevo Operador",
            "rol": RolUsuario.OPERADOR_HOSPEDAJE.value,
            "password": "PasswordSeguro123!"
        }
    )
    assert create_res.status_code == 403
    assert "Permisos insuficientes" in create_res.json()["detail"]


@pytest.mark.asyncio
async def test_admin_crea_usuario_con_envio_de_credenciales(client: AsyncClient, db_session: AsyncSession):
    """Verifica que el admin cree un usuario, se envíe el correo y se registre credenciales_enviadas."""
    # Crear admin
    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        admin = await usuario_service.create_user(
            db_session,
            UserCreate(
                email="admin2@oruro.gob.bo",
                nombre_completo="Admin Secundario",
                rol=RolUsuario.ADMIN_DEPARTAMENTAL,
                password="PasswordSeguro123!"
            )
        )

    login_res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": "admin2@oruro.gob.bo", "password": "PasswordSeguro123!"}
    )
    admin_token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        nuevo_user_res = await client.post(
            f"{settings.API_V1_STR}/usuarios/",
            headers=admin_headers,
            json={
                "email": "hotel_virgen_socavon@gmail.com",
                "nombre_completo": "Encargado Virgen del Socavón",
                "rol": RolUsuario.OPERADOR_HOSPEDAJE.value
                # Contraseña omitida: se genera automáticamente y se envía por correo
            }
        )
        assert nuevo_user_res.status_code == 201
        data = nuevo_user_res.json()
        assert data["email"] == "hotel_virgen_socavon@gmail.com"
        assert data["credenciales_enviadas"] is True
        mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_validacion_contrasena_debil_agetic(client: AsyncClient, db_session: AsyncSession):
    """Verifica que las contraseñas débiles que no cumplan la política AGETIC sean rechazadas con 422."""
    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        await usuario_service.create_user(
            db_session,
            UserCreate(
                email="admin_val@oruro.gob.bo",
                nombre_completo="Admin Validador",
                rol=RolUsuario.ADMIN_DEPARTAMENTAL,
                password="PasswordSeguro123!"
            )
        )

    login_res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": "admin_val@oruro.gob.bo", "password": "PasswordSeguro123!"}
    )
    admin_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Contraseña sin caracteres especiales ni mayúsculas
    res_debil = await client.post(
        f"{settings.API_V1_STR}/usuarios/",
        headers=admin_headers,
        json={
            "email": "hotel_invalido@gmail.com",
            "nombre_completo": "Hotel Invalido",
            "rol": RolUsuario.OPERADOR_HOSPEDAJE.value,
            "password": "simplepassword"
        }
    )
    assert res_debil.status_code == 422
