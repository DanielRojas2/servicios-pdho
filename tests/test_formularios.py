import io
from unittest.mock import AsyncMock, patch
from PIL import Image
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.establecimientos.schemas import EstablecimientoCreateConOperador
from app.modules.establecimientos.service import establecimiento_service
from app.modules.nacionalidades.models import Nacionalidad
from app.modules.usuarios.models import RolUsuario
from app.modules.usuarios.schemas import UserCreate
from app.modules.usuarios.service import usuario_service


def _generar_imagen_bytes() -> bytes:
    """Genera bytes de una imagen válida en memoria para pruebas sin archivos externos."""
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color=(240, 240, 240))
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _crear_token_usuario(client: AsyncClient, email: str, password: str) -> str:
    """Helper para autenticar y obtener el Bearer Token."""
    res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": email, "password": password}
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
async def setup_ambiente_hotel(client: AsyncClient, db_session: AsyncSession):
    """Fixture que crea nacionalidades base, administrador, establecimiento y operador titular."""
    # 1. Nacionalidades
    nac_bo = Nacionalidad(pais="Bolivia", cod_pais="BO", continente="América")
    nac_ar = Nacionalidad(pais="Argentina", cod_pais="AR", continente="América")
    db_session.add_all([nac_bo, nac_ar])
    await db_session.commit()
    await db_session.refresh(nac_bo)
    await db_session.refresh(nac_ar)

    # 2. Admin Departamental
    with patch("app.modules.usuarios.service.send_user_credentials_email", new_callable=AsyncMock) as m_email:
        m_email.return_value = True
        await usuario_service.create_user(
            db_session,
            UserCreate(
                email="admin_dept@oruro.gob.bo",
                nombre_completo="Admin Departamental",
                rol=RolUsuario.ADMIN_DEPARTAMENTAL,
                password="AdminPassword123!"
            ),
            send_email=False
        )

    admin_token = await _crear_token_usuario(client, "admin_dept@oruro.gob.bo", "AdminPassword123!")

    # 3. Crear Establecimiento "El Imperio de Carlos V" con su Operador
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m_email:
        m_email.return_value = True
        est_res = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="El Imperio de Carlos V",
                direccion="La Plata 6364, Aldana",
                categoria="1 Estrella",
                latitud=-17.9689,
                longitud=-67.1123,
                telefono="52-58446",
                total_plazas=21,
                operador_nombre_completo="Carlos Operador",
                operador_email="carlos_imperio@hotel.bo",
                operador_password="HotelPassword123!"
            )
        )

    operador_token = await _crear_token_usuario(client, "carlos_imperio@hotel.bo", "HotelPassword123!")
    headers_op = {"Authorization": f"Bearer {operador_token}"}

    # Obtener catálogo de tipos de habitación
    res_tipos = await client.get(f"{settings.API_V1_STR}/establecimientos/tipos-habitacion", headers=headers_op)
    tipos = res_tipos.json()
    tipo_mat = next(t for t in tipos if t["tipo_habitacion"] == "matrimonial")
    tipo_doble = next(t for t in tipos if t["tipo_habitacion"] == "doble")
    tipo_mult = next(t for t in tipos if t["tipo_habitacion"] == "multiple")

    # Configurar capacidad instalada de 9 habitaciones (conforme a la foto física)
    await client.put(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/capacidad",
        headers=headers_op,
        json={
            "habitaciones": [
                {"id_tipo_habitacion": tipo_mat["id"], "cant_habitaciones": 3, "nro_camas": 3},
                {"id_tipo_habitacion": tipo_doble["id"], "cant_habitaciones": 3, "nro_camas": 6},
                {"id_tipo_habitacion": tipo_mult["id"], "cant_habitaciones": 3, "nro_camas": 12},
            ]
        }
    )

    return {
        "admin_token": admin_token,
        "operador_token": operador_token,
        "establecimiento_id": est_res.id,
        "id_bolivia": nac_bo.id,
        "id_argentina": nac_ar.id,
    }


@pytest.mark.asyncio
async def test_creacion_manual_desde_cero_estadistica_hotelera_y_respaldo(
    client: AsyncClient,
    setup_ambiente_hotel: dict
):
    """
    Verifica la creación manual desde cero de Estadísticas Hoteleras:
    1. Carga manual de fecha/período, personal y movimientos de huéspedes.
    2. Subida de imagen como respaldo y conversión interna a PDF.
    3. Validación y recálculo estricto de las sumatorias del resumen.
    4. Edición/actualización mediante PUT.
    """
    tokens = setup_ambiente_hotel
    headers = {"Authorization": f"Bearer {tokens['operador_token']}"}

    # PASO 1: Subir imagen previa de respaldo independiente (opcional)
    img_bytes = _generar_imagen_bytes()
    files = {"file": ("respaldo_planilla_000360.jpg", img_bytes, "image/jpeg")}
    res_respaldo = await client.post(
        f"{settings.API_V1_STR}/formularios/subir-respaldo?tipo_formulario=estadistica",
        headers=headers,
        files=files
    )
    assert res_respaldo.status_code == 200
    data_respaldo = res_respaldo.json()
    assert data_respaldo["archivo_foto"].endswith(".jpg")
    assert data_respaldo["archivo_pdf"].endswith(".pdf")

    # PASO 2: Creación desde cero de la declaración manual
    detalles_huespedes = [
        # Bolivia (id_bolivia)
        {"dia": 14, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 2, "cant_permanencias": 0},
        {"dia": 15, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 0, "cant_permanencias": 2},
        {"dia": 16, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 0, "cant_permanencias": 2},
        {"dia": 17, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 0, "cant_permanencias": 2},
        {"dia": 18, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 0, "cant_permanencias": 2},
        # Argentina (id_argentina)
        {"dia": 25, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 1, "cant_permanencias": 0},
        {"dia": 26, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 0, "cant_permanencias": 1},
        {"dia": 27, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 0, "cant_permanencias": 1},
        {"dia": 28, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 0, "cant_permanencias": 1},
        {"dia": 29, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 0, "cant_permanencias": 1},
        {"dia": 30, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 0, "cant_permanencias": 1},
        {"dia": 31, "id_nacionalidad": tokens["id_argentina"], "cant_ingresos": 0, "cant_permanencias": 1},
    ]

    payload_creacion = {
        "numero_formulario": "000360",
        "mes": "Agosto",
        "gestion": 2026,
        "fecha_presentacion": "2026-09-07",
        "cant_emp_perma": 0,
        "cant_emp_event": 2,
        "archivo_foto": data_respaldo["archivo_foto"],
        "archivo_pdf": data_respaldo["archivo_pdf"],
        "observaciones": "Declaración manual con respaldo digitalizado adjunto",
        "detalles": detalles_huespedes
    }

    res_post = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers,
        json=payload_creacion
    )
    assert res_post.status_code == 201
    form_data = res_post.json()

    assert form_data["numero_formulario"] == "000360"
    assert form_data["estado"] == "ENVIADO"
    assert form_data["total_empleados"] == 2

    # Secciones A y C mapeadas
    assert form_data["seccion_a"]["nombre_establecimiento"] == "El Imperio de Carlos V"
    assert form_data["seccion_c"]["total_habitaciones"] == 9
    assert form_data["seccion_c"]["total_plazas"] == 21

    # Exactitud matemática del resumen
    assert form_data["r_ingreso_nals"] == 2
    assert form_data["r_permanencia_nals"] == 8
    assert form_data["total_nals"] == 10

    assert form_data["r_ingreso_extr"] == 1
    assert form_data["r_permanencia_extr"] == 6
    assert form_data["total_extr"] == 7

    assert form_data["total_ing"] == 3
    assert form_data["total_perm"] == 14
    assert form_data["total"] == 17

    # PASO 3: Editar formulario vía PUT
    form_id = form_data["id"]
    payload_update = {
        "observaciones": "Observación actualizada por el operador hotelero",
        "cant_emp_perma": 1
    }
    res_put = await client.put(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/{form_id}",
        headers=headers,
        json=payload_update
    )
    assert res_put.status_code == 200
    assert res_put.json()["observaciones"] == "Observación actualizada por el operador hotelero"
    assert res_put.json()["total_empleados"] == 3  # 1 permanente + 2 eventuales

    # PASO 4: Adjuntar una nueva foto de respaldo directamente al formulario
    files_new = {"file": ("nuevo_respaldo.jpg", _generar_imagen_bytes(), "image/jpeg")}
    res_adj = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/{form_id}/respaldo",
        headers=headers,
        files=files_new
    )
    assert res_adj.status_code == 200
    assert res_adj.json()["archivo_pdf"].endswith(".pdf")


@pytest.mark.asyncio
async def test_creacion_manual_ocupacion_hotelera_y_edicion(
    client: AsyncClient,
    setup_ambiente_hotel: dict
):
    """
    Verifica la creación manual desde cero de Ocupación Hotelera:
    1. Carga de días con habitaciones y personas ocupadas.
    2. Sumatoria total automática.
    3. Validación contra capacidad máxima de habitaciones.
    4. Edición vía PUT y adjunto de respaldo.
    """
    tokens = setup_ambiente_hotel
    headers = {"Authorization": f"Bearer {tokens['operador_token']}"}

    # Creación manual de Ocupación Hotelera
    detalles_ocup = [
        {"dia": 14, "hab_ocupadas": 2, "cant_personas": 2},
        {"dia": 15, "hab_ocupadas": 2, "cant_personas": 2},
        {"dia": 16, "hab_ocupadas": 2, "cant_personas": 2},
        {"dia": 17, "hab_ocupadas": 2, "cant_personas": 2},
        {"dia": 18, "hab_ocupadas": 2, "cant_personas": 2},
        {"dia": 25, "hab_ocupadas": 1, "cant_personas": 1},
        {"dia": 26, "hab_ocupadas": 1, "cant_personas": 1},
        {"dia": 27, "hab_ocupadas": 1, "cant_personas": 1},
        {"dia": 28, "hab_ocupadas": 1, "cant_personas": 1},
        {"dia": 29, "hab_ocupadas": 1, "cant_personas": 1},
        {"dia": 30, "hab_ocupadas": 1, "cant_personas": 1},
        {"dia": 31, "hab_ocupadas": 1, "cant_personas": 1},
    ]

    payload_creacion = {
        "mes": "Agosto",
        "gestion": 2026,
        "fecha_presentacion": "2026-09-07",
        "observaciones": "Planilla manual de ocupación",
        "detalles": detalles_ocup
    }

    res_post = await client.post(
        f"{settings.API_V1_STR}/ocupacion-hotelera/",
        headers=headers,
        json=payload_creacion
    )
    assert res_post.status_code == 201
    ocup_data = res_post.json()

    assert ocup_data["total_hab_ocupadas"] == 17
    assert ocup_data["total_personas"] == 17
    assert ocup_data["estado"] == "ENVIADO"

    # Edición mediante PUT
    ocup_id = ocup_data["id"]
    res_put = await client.put(
        f"{settings.API_V1_STR}/ocupacion-hotelera/{ocup_id}",
        headers=headers,
        json={"observaciones": "Ocupación corregida"}
    )
    assert res_put.status_code == 200
    assert res_put.json()["observaciones"] == "Ocupación corregida"

    # Adjuntar respaldo
    files = {"file": ("respaldo_ocupacion.jpg", _generar_imagen_bytes(), "image/jpeg")}
    res_resp = await client.post(
        f"{settings.API_V1_STR}/ocupacion-hotelera/{ocup_id}/respaldo",
        headers=headers,
        files=files
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["archivo_pdf"].endswith(".pdf")


@pytest.mark.asyncio
async def test_aislamiento_multitenant_de_formularios(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_ambiente_hotel: dict
):
    """
    Verifica que un operador de otro hotel no pueda consultar ni modificar
    los formularios de otro establecimiento.
    """
    tokens = setup_ambiente_hotel

    # Crear un segundo establecimiento con su respectivo operador
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m_email:
        m_email.return_value = True
        est2 = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Sucre Oruro",
                direccion="Calle 6 de Octubre #400",
                categoria="2 Estrellas",
                total_plazas=15,
                operador_nombre_completo="Maria Operadora",
                operador_email="maria_sucre@hotel.bo",
                operador_password="Hotel2Password123!"
            )
        )

    operador2_token = await _crear_token_usuario(client, "maria_sucre@hotel.bo", "Hotel2Password123!")

    # Operador 1 guarda su formulario de Estadísticas
    headers_op1 = {"Authorization": f"Bearer {tokens['operador_token']}"}
    payload_form = {
        "numero_formulario": "000500",
        "mes": "Julio",
        "gestion": 2026,
        "fecha_presentacion": "2026-08-05",
        "cant_emp_perma": 1,
        "cant_emp_event": 1,
        "detalles": [
            {"dia": 10, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 1, "cant_permanencias": 1}
        ]
    }
    res_crear = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers_op1,
        json=payload_form
    )
    assert res_crear.status_code == 201
    form_id = res_crear.json()["id"]

    # Operador 2 intenta acceder al formulario de Operador 1 por ID -> debe ser 403 Forbidden
    headers_op2 = {"Authorization": f"Bearer {operador2_token}"}
    res_acceso = await client.get(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/{form_id}",
        headers=headers_op2
    )
    assert res_acceso.status_code == 403

    # Operador 2 intenta modificar el formulario de Operador 1 -> 403 Forbidden
    res_mod = await client.put(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/{form_id}",
        headers=headers_op2,
        json={"observaciones": "Intento no autorizado"}
    )
    assert res_mod.status_code == 403

    # Al listar formularios, Operador 2 no ve el formulario del Operador 1
    res_list = await client.get(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers_op2
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) == 0

    # Admin Departamental sí puede verlo
    headers_admin = {"Authorization": f"Bearer {tokens['admin_token']}"}
    res_admin = await client.get(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/{form_id}",
        headers=headers_admin
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["id"] == form_id


@pytest.mark.asyncio
async def test_periodos_disponibles_calendario_real(
    client: AsyncClient,
    setup_ambiente_hotel: dict
):
    """
    Verifica que el endpoint /formularios/periodos-disponibles retorne:
    1. Cantidad real de días según calendario (ej: Febrero 28 días, Abril 30 días, etc.).
    2. En la gestión actual (2026), solo permite meses concluidos pasados (Enero a Septiembre).
    3. En gestiones pasadas (2025), permite de Enero a Diciembre.
    """
    tokens = setup_ambiente_hotel
    headers = {"Authorization": f"Bearer {tokens['operador_token']}"}

    # 1. Consultar gestión actual 2026 (estando en Octubre 2026)
    res_2026 = await client.get(
        f"{settings.API_V1_STR}/formularios/periodos-disponibles?gestion=2026",
        headers=headers
    )
    assert res_2026.status_code == 200
    data_2026 = res_2026.json()
    meses_2026 = {m["mes"]: m for m in data_2026["meses"]}

    # Días reales según calendario
    assert meses_2026["Enero"]["dias_en_mes"] == 31
    assert meses_2026["Febrero"]["dias_en_mes"] == 28
    assert meses_2026["Abril"]["dias_en_mes"] == 30
    assert meses_2026["Agosto"]["dias_en_mes"] == 31

    # Permisos en 2026: Enero a Septiembre permitidos (si no están declarados)
    assert meses_2026["Enero"]["permitido"] is True
    assert meses_2026["Septiembre"]["permitido"] is True

    # Octubre (mes actual) y Noviembre/Diciembre (futuros) no permitidos
    assert meses_2026["Octubre"]["permitido"] is False
    assert meses_2026["Noviembre"]["permitido"] is False
    assert meses_2026["Diciembre"]["permitido"] is False

    # 2. Consultar gestión pasada 2025
    res_2025 = await client.get(
        f"{settings.API_V1_STR}/formularios/periodos-disponibles?gestion=2025",
        headers=headers
    )
    assert res_2025.status_code == 200
    data_2025 = res_2025.json()
    # Todos los meses de 2025 deben estar permitidos
    for m in data_2025["meses"]:
        assert m["permitido"] is True


@pytest.mark.asyncio
async def test_validacion_dias_reales_segun_mes_y_gestion(
    client: AsyncClient,
    setup_ambiente_hotel: dict
):
    """
    Valida que no se puedan ingresar días que no existen en el calendario real:
    - Febrero 2026 solo tiene 28 días (día 29 debe dar 400 Bad Request).
    - Abril 2026 solo tiene 30 días (día 31 debe dar 400 Bad Request).
    """
    tokens = setup_ambiente_hotel
    headers = {"Authorization": f"Bearer {tokens['operador_token']}"}

    # Intentar declarar día 29 en Febrero 2026 (no bisiesto -> máximo 28)
    payload_febrero_invalido = {
        "numero_formulario": "000100",
        "mes": "Febrero",
        "gestion": 2026,
        "fecha_presentacion": "2026-03-05",
        "detalles": [
            {"dia": 29, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 1, "cant_permanencias": 0}
        ]
    }
    res_feb = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers,
        json=payload_febrero_invalido
    )
    assert res_feb.status_code == 400
    assert "máximo real de 28 días" in res_feb.json()["detail"]

    # Intentar declarar día 31 en Abril 2026 (máximo 30 días)
    payload_abril_invalido = {
        "numero_formulario": "000101",
        "mes": "Abril",
        "gestion": 2026,
        "fecha_presentacion": "2026-05-02",
        "detalles": [
            {"dia": 31, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 1, "cant_permanencias": 0}
        ]
    }
    res_abr = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers,
        json=payload_abril_invalido
    )
    assert res_abr.status_code == 400
    assert "máximo real de 30 días" in res_abr.json()["detail"]


@pytest.mark.asyncio
async def test_validacion_periodos_futuros_y_unicidad_periodo(
    client: AsyncClient,
    setup_ambiente_hotel: dict
):
    """
    Valida:
    1. Que no se puedan declarar meses futuros o en curso de la gestión actual.
    2. Que no se pueda duplicar el mismo formulario si ya fue declarado (unicidad).
    """
    tokens = setup_ambiente_hotel
    headers = {"Authorization": f"Bearer {tokens['operador_token']}"}

    # Intentar declarar mes futuro: Noviembre 2026
    payload_futuro = {
        "numero_formulario": "000200",
        "mes": "Noviembre",
        "gestion": 2026,
        "fecha_presentacion": "2026-12-01",
        "detalles": [
            {"dia": 5, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 1, "cant_permanencias": 0}
        ]
    }
    res_futuro = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers,
        json=payload_futuro
    )
    assert res_futuro.status_code == 400
    assert "solo se pueden declarar meses concluidos anteriores" in res_futuro.json()["detail"]

    # Registrar Mayo 2026 por primera vez -> 201 Created
    payload_mayo = {
        "numero_formulario": "000300",
        "mes": "Mayo",
        "gestion": 2026,
        "fecha_presentacion": "2026-06-05",
        "detalles": [
            {"dia": 10, "id_nacionalidad": tokens["id_bolivia"], "cant_ingresos": 2, "cant_permanencias": 0}
        ]
    }
    res_mayo = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers,
        json=payload_mayo
    )
    assert res_mayo.status_code == 201

    # Intentar registrar Mayo 2026 por segunda vez -> 409 Conflict (unicidad respetada)
    res_dup = await client.post(
        f"{settings.API_V1_STR}/estadisticas-hoteleras/",
        headers=headers,
        json=payload_mayo
    )
    assert res_dup.status_code == 409
    assert "ya fue registrado previamente" in res_dup.json()["detail"]

    # Verificar que el endpoint de periodos-disponibles marque Mayo 2026 como declarado=True y permitido=False
    res_disp = await client.get(
        f"{settings.API_V1_STR}/formularios/periodos-disponibles?gestion=2026",
        headers=headers
    )
    mayo_info = next(m for m in res_disp.json()["meses"] if m["mes"] == "Mayo")
    assert mayo_info["declarado"] is True
    assert mayo_info["permitido"] is False
