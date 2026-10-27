import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.nacionalidades.service import nacionalidad_service
from app.modules.usuarios.models import RolUsuario
from app.modules.usuarios.schemas import UserCreate
from app.modules.usuarios.service import usuario_service


async def _crear_usuario_y_token(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    rol: RolUsuario,
) -> str:
    """Helper para crear un usuario de prueba en memoria y obtener su token JWT."""
    password = "PasswordSeguro123!"
    await usuario_service.create_user(
        db_session,
        UserCreate(
            email=email,
            nombre_completo=f"Usuario {rol.value}",
            rol=rol,
            password=password,
        ),
        send_email=False,
    )
    login_res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_seed_catalogo_nacionalidades_e_idempotencia(
    client: AsyncClient, db_session: AsyncSession
):
    """Verifica que el seeder pueble el catálogo oficial y que sea completamente idempotente."""
    admin_token = await _crear_usuario_y_token(
        client, db_session, "admin_seed@oruro.gob.bo", RolUsuario.ADMIN_DEPARTAMENTAL
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Ejecutar seeding inicial
    res_seed = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/seed",
        headers=headers,
    )
    assert res_seed.status_code == 200
    data = res_seed.json()
    assert data["nuevos_insertados"] > 25
    assert data["existentes_omitidos"] == 0
    total_inicial = data["total_catalogo"]

    # 2. Verificar que las opciones requeridas existan explícitamente
    opciones_requeridas = [
        "Bolivia",
        "Otros America",
        "Otros Europa",
        "Otros Asia",
        "Otros",
        "Oceanía",
        "EE.UU.",
        "Inglaterra",
        "Holanda",
    ]
    for nombre in opciones_requeridas:
        res_check = await client.get(
            f"{settings.API_V1_STR}/nacionalidades/?search={nombre}",
            headers=headers,
        )
        assert res_check.status_code == 200
        nacs = res_check.json()
        assert any(n["pais"] == nombre for n in nacs), f"No se encontró '{nombre}' en el catálogo."

    # 3. Idempotencia: ejecutar nuevamente el seeder no debe duplicar registros
    res_seed2 = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/seed",
        headers=headers,
    )
    assert res_seed2.status_code == 200
    data2 = res_seed2.json()
    assert data2["nuevos_insertados"] == 0
    assert data2["existentes_omitidos"] == total_inicial
    assert data2["total_catalogo"] == total_inicial


@pytest.mark.asyncio
async def test_listar_nacionalidades_filtros_y_busqueda(
    client: AsyncClient, db_session: AsyncSession
):
    """Verifica la búsqueda por texto, código y filtros por continente."""
    admin_token = await _crear_usuario_y_token(
        client, db_session, "admin_filter@oruro.gob.bo", RolUsuario.ADMIN_DEPARTAMENTAL
    )
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post(f"{settings.API_V1_STR}/nacionalidades/seed", headers=headers)

    # Búsqueda por nombre de país
    res_arg = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?search=Argentina", headers=headers
    )
    assert res_arg.status_code == 200
    assert any(n["cod_pais"] == "AR" for n in res_arg.json())

    # Búsqueda por código ISO
    res_iso = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?search=BO", headers=headers
    )
    assert res_iso.status_code == 200
    assert any(n["pais"] == "Bolivia" for n in res_iso.json())

    # Búsqueda de categorías "Otros"
    res_otros = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?search=Otros", headers=headers
    )
    assert res_otros.status_code == 200
    nombres_otros = [n["pais"] for n in res_otros.json()]
    assert "Otros America" in nombres_otros
    assert "Otros Europa" in nombres_otros
    assert "Otros Asia" in nombres_otros
    assert "Otros" in nombres_otros

    # Filtro por continente
    res_europa = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?continente=Europa", headers=headers
    )
    assert res_europa.status_code == 200
    items_europa = res_europa.json()
    assert len(items_europa) > 5
    assert all(n["continente"] == "Europa" for n in items_europa)


@pytest.mark.asyncio
async def test_obtener_nacionalidad_por_id_y_codigo(
    client: AsyncClient, db_session: AsyncSession
):
    """Verifica consulta puntual por ID y por código de país (RN-7)."""
    admin_token = await _crear_usuario_y_token(
        client, db_session, "admin_lookup@oruro.gob.bo", RolUsuario.ADMIN_DEPARTAMENTAL
    )
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post(f"{settings.API_V1_STR}/nacionalidades/seed", headers=headers)

    # Por código BO
    res_bo = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/codigo/BO", headers=headers
    )
    assert res_bo.status_code == 200
    bo_data = res_bo.json()
    assert bo_data["pais"] == "Bolivia"
    assert bo_data["cod_pais"] == "BO"

    # Por código XAM (Otros America)
    res_xam = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/codigo/XAM", headers=headers
    )
    assert res_xam.status_code == 200
    xam_data = res_xam.json()
    assert xam_data["pais"] == "Otros America"
    assert xam_data["cod_pais"] == "XAM"

    # Por ID
    bo_id = bo_data["id"]
    res_id = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/{bo_id}", headers=headers
    )
    assert res_id.status_code == 200
    assert res_id.json()["pais"] == "Bolivia"

    # Código inexistente -> 404
    res_inexistente = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/codigo/ZZZZ", headers=headers
    )
    assert res_inexistente.status_code == 404


@pytest.mark.asyncio
async def test_crud_nacionalidad_admin_y_restriccion_roles(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Verifica que el Administrador pueda crear, editar y deshabilitar nacionalidades,
    y que los operadores tengan restringidas las mutaciones.
    """
    admin_token = await _crear_usuario_y_token(
        client, db_session, "admin_crud@oruro.gob.bo", RolUsuario.ADMIN_DEPARTAMENTAL
    )
    operador_token = await _crear_usuario_y_token(
        client, db_session, "operador_crud@hotel.com", RolUsuario.OPERADOR_HOSPEDAJE
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    operador_headers = {"Authorization": f"Bearer {operador_token}"}

    # 1. Operador intenta crear nacionalidad -> 403 Forbidden
    payload_nuevo = {
        "pais": "Pais Fantasia",
        "cod_pais": "PF",
        "continente": "Otros",
        "activo": True,
    }
    res_op = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/",
        json=payload_nuevo,
        headers=operador_headers,
    )
    assert res_op.status_code == 403

    # 2. Administrador crea nacionalidad -> 201 Created
    res_admin = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/",
        json=payload_nuevo,
        headers=admin_headers,
    )
    assert res_admin.status_code == 201
    nac_creada = res_admin.json()
    assert nac_creada["pais"] == "Pais Fantasia"
    assert nac_creada["cod_pais"] == "PF"
    nac_id = nac_creada["id"]

    # 3. Validar duplicidad de código o nombre -> 400 Bad Request
    res_dup = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/",
        json=payload_nuevo,
        headers=admin_headers,
    )
    assert res_dup.status_code == 400

    # 4. Administrador actualiza parcialmente
    res_patch = await client.patch(
        f"{settings.API_V1_STR}/nacionalidades/{nac_id}",
        json={"pais": "Pais Fantasia Renovado"},
        headers=admin_headers,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["pais"] == "Pais Fantasia Renovado"

    # 5. Administrador deshabilita (Soft delete)
    res_del = await client.delete(
        f"{settings.API_V1_STR}/nacionalidades/{nac_id}",
        headers=admin_headers,
    )
    assert res_del.status_code == 204

    # 6. Al listar activos, no debe figurar; al listar todos (solo_activos=False), sí figura
    res_activos = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?search=Fantasia&solo_activos=true",
        headers=admin_headers,
    )
    assert len(res_activos.json()) == 0

    res_todos = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?search=Fantasia&solo_activos=false",
        headers=admin_headers,
    )
    assert len(res_todos.json()) == 1
    assert res_todos.json()[0]["activo"] is False


@pytest.mark.asyncio
async def test_acceso_lectura_operador_y_dependiente(
    client: AsyncClient, db_session: AsyncSession
):
    """Verifica que operadores y dependientes puedan consultar el catálogo para llenar formularios."""
    admin_token = await _crear_usuario_y_token(
        client, db_session, "admin_cat@oruro.gob.bo", RolUsuario.ADMIN_DEPARTAMENTAL
    )
    await client.post(
        f"{settings.API_V1_STR}/nacionalidades/seed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    operador_token = await _crear_usuario_y_token(
        client, db_session, "operador_view@hotel.com", RolUsuario.OPERADOR_HOSPEDAJE
    )
    dependiente_token = await _crear_usuario_y_token(
        client, db_session, "dep_view@hotel.com", RolUsuario.DEPENDIENTE_HOSPEDAJE
    )

    # Operador puede consultar
    res_op = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?limit=10",
        headers={"Authorization": f"Bearer {operador_token}"},
    )
    assert res_op.status_code == 200
    assert len(res_op.json()) == 10

    # Dependiente puede consultar
    res_dep = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/?limit=10",
        headers={"Authorization": f"Bearer {dependiente_token}"},
    )
    assert res_dep.status_code == 200
    assert len(res_dep.json()) == 10
