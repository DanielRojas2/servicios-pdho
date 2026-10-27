from datetime import timedelta
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.establecimientos.schemas import EstablecimientoCreateConOperador
from app.modules.establecimientos.service import establecimiento_service
from app.modules.nacionalidades.models import Nacionalidad
from app.modules.usuarios.models import RolUsuario
from app.modules.usuarios.schemas import UserCreate
from app.modules.usuarios.service import usuario_service


async def _login_token(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": email, "password": password}
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
async def setup_seguridad_ambiente(client: AsyncClient, db_session: AsyncSession):
    """Fixture con administrador departamental y dos establecimientos aislados."""
    # 1. Admin Departamental
    await usuario_service.create_user(
        db_session,
        UserCreate(
            email="admin_sec@oruro.gob.bo",
            nombre_completo="Admin Seguridad AGETIC",
            rol=RolUsuario.ADMIN_DEPARTAMENTAL,
            password="AdminPassword123!"
        ),
        send_email=False
    )
    admin_token = await _login_token(client, "admin_sec@oruro.gob.bo", "AdminPassword123!")

    # 2. Hotel Alfa
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m:
        m.return_value = True
        est_alfa = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Alfa Seguridad",
                direccion="Calle Alfa 123",
                categoria="3 Estrellas",
                operador_nombre_completo="Operador Alfa",
                operador_email="alfa@seguridad.bo",
                operador_password="HotelPassword123!",
            )
        )
    token_alfa = await _login_token(client, "alfa@seguridad.bo", "HotelPassword123!")

    # 3. Hotel Beta
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m:
        m.return_value = True
        est_beta = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Beta Seguridad",
                direccion="Calle Beta 456",
                categoria="4 Estrellas",
                operador_nombre_completo="Operador Beta",
                operador_email="beta@seguridad.bo",
                operador_password="HotelPassword123!",
            )
        )
    token_beta = await _login_token(client, "beta@seguridad.bo", "HotelPassword123!")

    # 4. Semilla de nacionalidad
    nac = Nacionalidad(pais="Bolivia Sec", cod_pais="BO", continente="América")
    db_session.add(nac)
    await db_session.commit()

    return {
        "admin_token": admin_token,
        "token_alfa": token_alfa,
        "token_beta": token_beta,
        "est_alfa": est_alfa,
        "est_beta": est_beta,
    }


# ==============================================================================
# 1. AUDITORÍA DE CABECERAS DE SEGURIDAD HTTP (PISI / ISO 27001)
# ==============================================================================

@pytest.mark.asyncio
async def test_cabeceras_de_seguridad_http_en_respuestas(client: AsyncClient):
    """
    Verifica que el middleware inyecte obligatoriamente las 8 cabeceras de seguridad
    estándar en todas las respuestas de la API.
    """
    res = await client.get(f"{settings.API_V1_STR}/health")
    assert res.status_code == 200

    headers = res.headers

    # 1. Prevención de MIME Sniffing
    assert headers.get("X-Content-Type-Options") == "nosniff"

    # 2. Protección contra Clickjacking
    assert headers.get("X-Frame-Options") == "DENY"

    # 3. Filtro contra Cross-Site Scripting reflejado
    assert headers.get("X-XSS-Protection") == "1; mode=block"

    # 4. HSTS (HTTP Strict Transport Security)
    assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"

    # 5. Content Security Policy
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")

    # 6. Referrer Policy
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # 7. Permissions Policy
    assert "geolocation=()" in headers.get("Permissions-Policy", "")

    # 8. Ocultación del servidor web real
    assert headers.get("Server") == "PDHO-Secure-API"


# ==============================================================================
# 2. AUDITORÍA CONTRA INYECCIÓN SQL
# ==============================================================================

@pytest.mark.asyncio
async def test_resistencia_contra_inyeccion_sql(client: AsyncClient, setup_seguridad_ambiente):
    """
    Verifica que parámetros maliciosos con inyecciones SQL no ejecuten código
    ni provoquen excepciones internas 500 no controladas.
    """
    token = setup_seguridad_ambiente["admin_token"]

    payloads_inyeccion = [
        "' OR '1'='1",
        "'; DROP TABLE usuarios; --",
        "1' UNION SELECT null, null, null, null, null --",
        "' AND 1=0 UNION ALL SELECT 'admin', 'pass' --",
        "admin'--",
    ]

    for payload in payloads_inyeccion:
        # Búsqueda de nacionalidades con payload malicioso
        res = await client.get(
            f"{settings.API_V1_STR}/nacionalidades/?search={payload}",
            headers={"Authorization": f"Bearer {token}"}
        )
        # La consulta debe ser parametrizada y responder 200 (resultado vacío seguro) sin romperse
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # Filtro de reportes con payload malicioso en mes
        res_rep = await client.get(
            f"{settings.API_V1_STR}/reportes/graficos/nacionales-extranjeros?mes={payload}&gestion=2026",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Debe ser rechazado limpiamente como BadRequest (400) o Unprocessable (422), nunca un 500
        assert res_rep.status_code in [400, 422]


# ==============================================================================
# 3. POLÍTICA DE CONTRASEÑAS ROBUSTAS (AGETIC / PISLEA)
# ==============================================================================

@pytest.mark.asyncio
async def test_politica_contrasenas_robustas_agetic(client: AsyncClient, setup_seguridad_ambiente):
    """
    Verifica que se rechacen rigurosamente las contraseñas débiles que incumplan
    las directrices de AGETIC (mínimo 8 caracteres, mayúsculas, minúsculas, números y símbolos).
    """
    token = setup_seguridad_ambiente["admin_token"]

    contrasenas_debiles = [
        ("1234", "Demasiado corta"),
        ("password123!", "Sin mayúscula"),
        ("PASSWORD123!", "Sin minúscula"),
        ("PasswordSegura!", "Sin número"),
        ("PasswordSegura1", "Sin caracter especial"),
        ("12345678", "Solo números"),
    ]

    for pwd_invalida, motivo in contrasenas_debiles:
        res = await client.post(
            f"{settings.API_V1_STR}/usuarios/",
            json={
                "email": f"test_pwd_{abs(hash(pwd_invalida))}@test.bo",
                "nombre_completo": "Usuario Test",
                "rol": "OPERADOR_HOSPEDAJE",
                "password": pwd_invalida
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code in [400, 422], f"Se esperaba rechazo (400 o 422) para contraseña inválida: '{pwd_invalida}' ({motivo})"
        detail_text = str(res.json()).lower()
        assert any(term in detail_text for term in ["contraseña", "password", "least", "caracter", "longitud"])


# ==============================================================================
# 4. AUDITORÍA CRIPTOGRÁFICA DE TOKENS JWT
# ==============================================================================

@pytest.mark.asyncio
async def test_rechazo_de_tokens_jwt_adulterados_expirados_y_malformados(client: AsyncClient, setup_seguridad_ambiente):
    """
    Verifica que cualquier token firmado con secreto incorrecto, expirado o adulterado
    sea rechazado de inmediato con HTTP 401 Unauthorized.
    """
    token_legitimo = setup_seguridad_ambiente["admin_token"]

    # 1. Token con firma manipulada (adulterado)
    token_adulterado = token_legitimo[:-5] + "XXXXX"
    res_adulterado = await client.get(
        f"{settings.API_V1_STR}/usuarios/me",
        headers={"Authorization": f"Bearer {token_adulterado}"}
    )
    assert res_adulterado.status_code == 401

    # 2. Token malformado
    res_malformado = await client.get(
        f"{settings.API_V1_STR}/usuarios/me",
        headers={"Authorization": "Bearer esto-no-es-un-jwt-valido"}
    )
    assert res_malformado.status_code == 401

    # 3. Token expirado en el pasado
    token_expirado = create_access_token(
        subject="1",
        expires_delta=timedelta(seconds=-10)
    )
    res_expirado = await client.get(
        f"{settings.API_V1_STR}/usuarios/me",
        headers={"Authorization": f"Bearer {token_expirado}"}
    )
    assert res_expirado.status_code == 401

    # 4. Petición sin cabecera Authorization
    res_sin_auth = await client.get(f"{settings.API_V1_STR}/usuarios/me")
    assert res_sin_auth.status_code == 401


# ==============================================================================
# 5. AISLAMIENTO MULTI-TENANT Y PERMISOS RBAC
# ==============================================================================

@pytest.mark.asyncio
async def test_aislamiento_multi_tenant_entre_establecimientos(client: AsyncClient, setup_seguridad_ambiente):
    """
    Verifica que el Operador del Hotel Alfa no pueda mutar ni espiar información del Hotel Beta.
    """
    token_alfa = setup_seguridad_ambiente["token_alfa"]
    est_beta = setup_seguridad_ambiente["est_beta"]

    # 1. Operador Alfa intenta solicitar estadísticas forzando el ID del Hotel Beta -> 403 Forbidden
    res_reporte_ajeno = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionales-extranjeros?id_establecimiento={est_beta.id}&gestion=2026",
        headers={"Authorization": f"Bearer {token_alfa}"}
    )
    assert res_reporte_ajeno.status_code == 403

    # 2. Operador Alfa intenta acceder a la bitácora institucional de cumplimiento (Rol Admin) -> 403 Forbidden
    res_cumplimiento = await client.get(
        f"{settings.API_V1_STR}/reportes/cumplimiento-declaraciones?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {token_alfa}"}
    )
    assert res_cumplimiento.status_code == 403

    # 3. Operador Alfa intenta dar de alta una nacionalidad oficial (Rol Admin) -> 403 Forbidden
    res_nac = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/",
        json={"pais": "País No Autorizado", "cod_pais": "XX", "continente": "América"},
        headers={"Authorization": f"Bearer {token_alfa}"}
    )
    assert res_nac.status_code == 403
