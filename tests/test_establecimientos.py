from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.establecimientos.models import TipoHabitacionEnum
from app.modules.establecimientos.schemas import (
    DependienteCreate,
    EstablecimientoCreateConOperador,
)
from app.modules.establecimientos.service import establecimiento_service
from app.modules.usuarios.models import RolUsuario
from app.modules.usuarios.schemas import UserCreate
from app.modules.usuarios.service import usuario_service


async def _crear_token_usuario(client: AsyncClient, email: str, password: str) -> str:
    """Helper para autenticar y obtener el Bearer Token."""
    res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": email, "password": password}
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_crea_establecimiento_con_operador(
    client: AsyncClient,
    db_session: AsyncSession
):
    """
    Verifica que el Administrador Departamental pueda dar de alta un establecimiento
    y su operador titular en una sola transacción, enviándole credenciales por correo.
    """
    # 1. Crear Admin
    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        await usuario_service.create_user(
            db_session,
            UserCreate(
                email="admin_dept@oruro.gob.bo",
                nombre_completo="Admin Departamental",
                rol=RolUsuario.ADMIN_DEPARTAMENTAL,
                password="PasswordSeguro123!"
            ),
            send_email=False
        )

    admin_token = await _crear_token_usuario(client, "admin_dept@oruro.gob.bo", "PasswordSeguro123!")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin registra establecimiento con su operador
    payload = {
        "nombre_establecimiento": "Gran Hotel Oruro",
        "direccion": "Calle Bolivar #123",
        "categoria": "4_estrellas",
        "latitud": -17.9647,
        "longitud": -67.1064,
        "telefono": "+591-2-5254321",
        "total_plazas": 45,
        "operador_nombre_completo": "Juan Perez Encargado",
        "operador_email": "juan.perez@granhoteloruro.bo",
        "operador_password": "PasswordHotel123!"
    }

    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        res = await client.post(
            f"{settings.API_V1_STR}/establecimientos/",
            json=payload,
            headers=headers
        )
        assert res.status_code == 201
        data = res.json()
        assert data["nombre_establecimiento"] == "Gran Hotel Oruro"
        assert data["categoria"] == "4_estrellas"
        assert data["total_plazas"] == 45
        assert data["total_habitaciones"] == 0
        assert data["operador"] is not None
        assert data["operador"]["email"] == "juan.perez@granhoteloruro.bo"
        assert data["operador"]["rol"] == RolUsuario.OPERADOR_HOSPEDAJE.value
        mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_operador_consulta_y_actualiza_su_establecimiento(
    client: AsyncClient,
    db_session: AsyncSession
):
    """
    Verifica que el OPERADOR_HOSPEDAJE pueda consultar la ficha técnica de su establecimiento
    y actualizar el total_plazas de forma manual.
    """
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock):
        est = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hostal Sagarnaga Oruro",
                direccion="Av. 6 de Octubre #45",
                categoria="hostal",
                total_plazas=20,
                operador_nombre_completo="Maria Gomez",
                operador_email="maria@sagarnaga.bo",
                operador_password="PasswordHotel123!"
            ),
            send_email=False
        )

    operador_token = await _crear_token_usuario(client, "maria@sagarnaga.bo", "PasswordHotel123!")
    headers = {"Authorization": f"Bearer {operador_token}"}

    # Consultar /mi-establecimiento
    res_get = await client.get(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento",
        headers=headers
    )
    assert res_get.status_code == 200
    assert res_get.json()["nombre_establecimiento"] == "Hostal Sagarnaga Oruro"
    assert res_get.json()["total_plazas"] == 20

    # Actualizar total_plazas de forma manual
    res_patch = await client.patch(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento",
        json={"total_plazas": 28, "telefono": "+591-72983748"},
        headers=headers
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["total_plazas"] == 28
    assert res_patch.json()["telefono"] == "+591-72983748"


@pytest.mark.asyncio
async def test_operador_configura_capacidad_y_calcula_total_habitaciones(
    client: AsyncClient,
    db_session: AsyncSession
):
    """
    Verifica que al registrar el desglose por tipo de habitación:
    - Se almacenen cant_habitaciones y nro_camas.
    - Se recalcula automáticamente total_habitaciones sumando cant_habitaciones (RN-2).
    """
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock):
        await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Terminal",
                direccion="Zona Terminal",
                categoria="2_estrellas",
                total_plazas=30,
                operador_nombre_completo="Carlos Lopez",
                operador_email="carlos@terminal.bo",
                operador_password="PasswordHotel123!"
            ),
            send_email=False
        )

    operador_token = await _crear_token_usuario(client, "carlos@terminal.bo", "PasswordHotel123!")
    headers = {"Authorization": f"Bearer {operador_token}"}

    # Obtener catálogo de tipos de habitación
    res_tipos = await client.get(
        f"{settings.API_V1_STR}/establecimientos/tipos-habitacion",
        headers=headers
    )
    assert res_tipos.status_code == 200
    tipos = res_tipos.json()
    assert len(tipos) >= 6

    tipo_simple = next(t for t in tipos if t["tipo_habitacion"] == TipoHabitacionEnum.SIMPLE.value)
    tipo_doble = next(t for t in tipos if t["tipo_habitacion"] == TipoHabitacionEnum.DOBLE.value)
    tipo_matrimonial = next(t for t in tipos if t["tipo_habitacion"] == TipoHabitacionEnum.MATRIMONIAL.value)

    # Configurar capacidad: 5 simples (5 camas), 3 dobles (6 camas), 2 matrimoniales (2 camas)
    payload_capacidad = {
        "habitaciones": [
            {"id_tipo_habitacion": tipo_simple["id"], "cant_habitaciones": 5, "nro_camas": 5},
            {"id_tipo_habitacion": tipo_doble["id"], "cant_habitaciones": 3, "nro_camas": 6},
            {"id_tipo_habitacion": tipo_matrimonial["id"], "cant_habitaciones": 2, "nro_camas": 2},
        ]
    }

    res_put = await client.put(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/capacidad",
        json=payload_capacidad,
        headers=headers
    )
    assert res_put.status_code == 200
    data = res_put.json()

    # Total habitaciones calculado automáticamente: 5 + 3 + 2 = 10
    assert data["total_habitaciones"] == 10
    assert len(data["habitaciones"]) == 3
    # Verificar nro_camas registrado en cada tipo
    simple_reg = next(h for h in data["habitaciones"] if h["id_tipo_habitacion"] == tipo_simple["id"])
    assert simple_reg["cant_habitaciones"] == 5
    assert simple_reg["nro_camas"] == 5


@pytest.mark.asyncio
async def test_aislamiento_de_dependientes_por_establecimiento(
    client: AsyncClient,
    db_session: AsyncSession
):
    """
    Verifica que:
    1. Un OPERADOR_HOSPEDAJE puede crear dependientes para su establecimiento.
    2. El nuevo dependiente tiene rol DEPENDIENTE_HOSPEDAJE.
    3. Un operador solo ve los dependientes de su propio establecimiento y NO los de otro.
    4. Un operador no puede modificar dependientes de otro establecimiento (404 / no acceso).
    """
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock):
        # Establecimiento A
        await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Alba",
                direccion="Calle Sucre #10",
                categoria="3_estrellas",
                operador_nombre_completo="Operador Hotel Alba",
                operador_email="operador@alba.bo",
                operador_password="PasswordHotel123!"
            ),
            send_email=False
        )

        # Establecimiento B
        await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Residencial Eden",
                direccion="Calle La Paz #20",
                categoria="residencial",
                operador_nombre_completo="Operador Eden",
                operador_email="operador@eden.bo",
                operador_password="PasswordHotel123!"
            ),
            send_email=False
        )

    token_alba = await _crear_token_usuario(client, "operador@alba.bo", "PasswordHotel123!")
    token_eden = await _crear_token_usuario(client, "operador@eden.bo", "PasswordHotel123!")

    headers_alba = {"Authorization": f"Bearer {token_alba}"}
    headers_eden = {"Authorization": f"Bearer {token_eden}"}

    # 1. Operador Alba crea un dependiente
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as mock_email:
        mock_email.return_value = True
        res_dep_alba = await client.post(
            f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes",
            json={
                "nombre_completo": "Recepcionista Turno Manana",
                "email": "recepcion@alba.bo",
                "password": "PasswordDep123!"
            },
            headers=headers_alba
        )
        assert res_dep_alba.status_code == 201
        dep_alba = res_dep_alba.json()
        assert dep_alba["rol"] == RolUsuario.DEPENDIENTE_HOSPEDAJE.value

    # 2. Operador Eden crea su propio dependiente
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as mock_eden:
        mock_eden.return_value = True
        res_dep_eden = await client.post(
            f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes",
            json={
                "nombre_completo": "Personal Eden",
                "email": "personal@eden.bo",
                "password": "PasswordDep123!"
            },
            headers=headers_eden
        )
        assert res_dep_eden.status_code == 201
        dep_eden = res_dep_eden.json()

    # 3. Operador Alba lista sus dependientes -> solo ve a 'recepcion@alba.bo'
    res_list_alba = await client.get(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes",
        headers=headers_alba
    )
    assert res_list_alba.status_code == 200
    emails_alba = [d["email"] for d in res_list_alba.json()]
    assert "recepcion@alba.bo" in emails_alba
    assert "personal@eden.bo" not in emails_alba

    # 4. Operador Eden lista sus dependientes -> solo ve a 'personal@eden.bo'
    res_list_eden = await client.get(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes",
        headers=headers_eden
    )
    assert res_list_eden.status_code == 200
    emails_eden = [d["email"] for d in res_list_eden.json()]
    assert "personal@eden.bo" in emails_eden
    assert "recepcion@alba.bo" not in emails_eden

    # 5. Operador Alba intenta modificar el dependiente de Eden -> 404 No encontrado en su establecimiento
    res_hack = await client.patch(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes/{dep_eden['id']}",
        json={"activo": False},
        headers=headers_alba
    )
    assert res_hack.status_code == 404


@pytest.mark.asyncio
async def test_dependiente_puede_acceder_pero_no_crear_otros_dependientes(
    client: AsyncClient,
    db_session: AsyncSession
):
    """
    Verifica que un DEPENDIENTE_HOSPEDAJE:
    - Puede iniciar sesión y consultar los datos de su establecimiento.
    - NO tiene permiso para registrar otros dependientes (403 Forbidden).
    - NO tiene permiso para reconfigurar la capacidad instalada (403 Forbidden).
    """
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock):
        est = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Alojamiento Pagador",
                direccion="Calle Pagador #55",
                categoria="alojamiento",
                operador_nombre_completo="Duenio Pagador",
                operador_email="duenio@pagador.bo",
                operador_password="PasswordHotel123!"
            ),
            send_email=False
        )
        # Crear dependiente para el establecimiento
        await establecimiento_service.crear_dependiente(
            db_session,
            establecimiento_id=est.id,
            dependiente_in=DependienteCreate(
                nombre_completo="Asistente Pagador",
                email="asistente@pagador.bo",
                password="PasswordDep123!"
            ),
            send_email=False
        )

    # Login como dependiente
    token_dep = await _crear_token_usuario(client, "asistente@pagador.bo", "PasswordDep123!")
    headers_dep = {"Authorization": f"Bearer {token_dep}"}

    # Puede consultar /mi-establecimiento
    res_get = await client.get(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento",
        headers=headers_dep
    )
    assert res_get.status_code == 200
    assert res_get.json()["nombre_establecimiento"] == "Alojamiento Pagador"

    # Intento de crear otro dependiente -> 403 Forbidden
    res_post_dep = await client.post(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes",
        json={"nombre_completo": "Otro", "email": "otro@pagador.bo"},
        headers=headers_dep
    )
    assert res_post_dep.status_code == 403

    # Intento de reconfigurar capacidad de habitaciones -> 403 Forbidden
    res_put_cap = await client.put(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/capacidad",
        json={"habitaciones": []},
        headers=headers_dep
    )
    assert res_put_cap.status_code == 403
