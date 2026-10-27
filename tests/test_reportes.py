from datetime import date
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.establecimientos.models import Establecimiento
from app.modules.establecimientos.schemas import EstablecimientoCreateConOperador
from app.modules.establecimientos.service import establecimiento_service
from app.modules.formularios.models import (
    DetalleEstadisticaHotelera,
    DetalleOcupacionHotelera,
    EstadisticaHotelera,
    EstadoFormulario,
    OcupacionHotelera,
)
from app.modules.nacionalidades.models import Nacionalidad
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


@pytest.fixture
async def setup_reportes_data(client: AsyncClient, db_session: AsyncSession):
    """
    Crea el conjunto de datos completo para pruebas de reportes:
    - 12 Nacionalidades (BO, AR, BR, CL, PE, US, ES, FR, DE, IT, GB, UY)
    - 2 Establecimientos (Hotel San Felipe con 20 habs, Gran Hotel Oruro con 30 habs)
    - Formularios de Estadísticas y Ocupación con matriz dispersa
    - Usuario Administrador Departamental y Operador
    """
    # 1. Nacionalidades
    paises_data = [
        ("Bolivia", "BO", "América"),
        ("Argentina", "AR", "América"),
        ("Brasil", "BR", "América"),
        ("Chile", "CL", "América"),
        ("Perú", "PE", "América"),
        ("EE.UU.", "US", "América"),
        ("España", "ES", "Europa"),
        ("Francia", "FR", "Europa"),
        ("Alemania", "DE", "Europa"),
        ("Italia", "IT", "Europa"),
        ("Inglaterra", "GB", "Europa"),
        ("Uruguay", "UY", "América"),
    ]
    nacionalidades = {}
    for pais, cod, cont in paises_data:
        nac = Nacionalidad(pais=pais, cod_pais=cod, continente=cont, activo=True)
        db_session.add(nac)
        await db_session.flush()
        nacionalidades[cod] = nac

    # 2. Admin Departamental
    await usuario_service.create_user(
        db_session,
        UserCreate(
            email="admin_reportes@oruro.gob.bo",
            nombre_completo="Admin Estadísticas Oruro",
            rol=RolUsuario.ADMIN_DEPARTAMENTAL,
            password="AdminPassword123!"
        ),
        send_email=False
    )
    admin_token = await _crear_token_usuario(client, "admin_reportes@oruro.gob.bo", "AdminPassword123!")

    # 3. Establecimiento 1: Hotel San Felipe (Declarará todo septiembre 2026)
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m_email:
        m_email.return_value = True
        est1_res = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel San Felipe",
                direccion="Calle Bolívar 100",
                categoria="3 Estrellas",
                total_plazas=40,
                operador_nombre_completo="Carlos San Felipe",
                operador_email="sanfelipe@hotel.bo",
                operador_password="HotelPassword123!",
            )
        )
    est1 = est1_res
    est1.total_habitaciones = 20
    db_session.add(est1)
    await db_session.commit()

    operador_token = await _crear_token_usuario(client, "sanfelipe@hotel.bo", "HotelPassword123!")

    # 4. Establecimiento 2: Gran Hotel Oruro (No declarará en septiembre para probar bitácora de mora)
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m_email:
        m_email.return_value = True
        est2_res = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Gran Hotel Oruro",
                direccion="Plaza 10 de Febrero",
                categoria="4 Estrellas",
                total_plazas=60,
                operador_nombre_completo="Mario Oruro",
                operador_email="granhotel@oruro.bo",
                operador_password="HotelPassword123!",
            )
        )
    est2 = est2_res
    est2.total_habitaciones = 30
    db_session.add(est2)
    await db_session.commit()

    # 5. Declaración de Estadísticas Hoteleras de Septiembre 2026 para Hotel San Felipe
    # Movimientos con distribución para probar ranking y torta:
    # BO (Bolivia): 100 ing, 200 perm -> 300 tot
    # AR (Argentina): 40 ing, 80 perm -> 120 tot
    # BR (Brasil): 30 ing, 60 perm -> 90 tot
    # CL (Chile): 20 ing, 40 perm -> 60 tot
    # PE (Perú): 15 ing, 30 perm -> 45 tot
    # US (EE.UU.): 10 ing, 20 perm -> 30 tot
    # ES (España): 8 ing, 16 perm -> 24 tot
    # FR (Francia): 6 ing, 12 perm -> 18 tot
    # DE (Alemania): 5 ing, 10 perm -> 15 tot
    # IT (Italia): 4 ing, 8 perm -> 12 tot
    # Puesto 11: GB (Inglaterra): 3 ing, 6 perm -> 9 tot
    # Puesto 12: UY (Uruguay): 2 ing, 4 perm -> 6 tot
    
    # Totales:
    # Nals (BO): ing=100, perm=200, tot=300
    # Extr (Resto): ing=143, perm=286, tot=429
    # Total ing: 243, Total perm: 486, Total gral: 729
    form_est = EstadisticaHotelera(
        numero_formulario="000100",
        id_establecimiento=est1.id,
        mes="septiembre",
        gestion=2026,
        fecha_presentacion=date(2026, 10, 5),
        cant_emp_perma=5,
        cant_emp_event=2,
        total_empleados=7,
        estado=EstadoFormulario.ENVIADO,
        r_ingreso_nals=100,
        r_ingreso_extr=143,
        r_permanencia_nals=200,
        r_permanencia_extr=286,
        total_nals=300,
        total_extr=429,
        total_ing=243,
        total_perm=486,
        total=729,
    )
    db_session.add(form_est)
    await db_session.flush()

    movimientos = [
        ("BO", 100, 200, 10),
        ("AR", 40, 80, 11),
        ("BR", 30, 60, 12),
        ("CL", 20, 40, 13),
        ("PE", 15, 30, 14),
        ("US", 10, 20, 15),
        ("ES", 8, 16, 16),
        ("FR", 6, 12, 17),
        ("DE", 5, 10, 18),
        ("IT", 4, 8, 19),
        ("GB", 3, 6, 20),
        ("UY", 2, 4, 21),
    ]

    for cod, ing, perm, dia in movimientos:
        det = DetalleEstadisticaHotelera(
            id_estadistica=form_est.id,
            id_nacionalidad=nacionalidades[cod].id,
            dia=dia,
            cant_ingresos=ing,
            cant_permanencias=perm,
        )
        db_session.add(det)

    # 6. Formulario de Ocupación Hotelera de Septiembre 2026 para Hotel San Felipe
    # 300 habitaciones ocupadas en el mes
    form_ocup = OcupacionHotelera(
        id_establecimiento=est1.id,
        mes="septiembre",
        gestion=2026,
        fecha_presentacion=date(2026, 10, 5),
        total_hab_ocupadas=300,
        total_personas=450,
        estado=EstadoFormulario.ENVIADO,
    )
    db_session.add(form_ocup)
    await db_session.flush()

    for dia in range(1, 31):
        det_ocup = DetalleOcupacionHotelera(
            id_ocupacion=form_ocup.id,
            dia=dia,
            hab_ocupadas=10,
            cant_personas=15,
        )
        db_session.add(det_ocup)

    await db_session.commit()

    return {
        "admin_token": admin_token,
        "operador_token": operador_token,
        "est1": est1,
        "est2": est2,
        "nacionalidades": nacionalidades,
    }


# ========================================================
# TESTS: 1. GRÁFICO DE TORTA (NACIONALES VS EXTRANJEROS)
# ========================================================

@pytest.mark.asyncio
async def test_grafico_torta_nacionales_extranjeros_mes_gestion(client: AsyncClient, setup_reportes_data):
    """Verifica el cálculo del gráfico de torta filtrando por mes y gestión."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionales-extranjeros?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["periodo"]["tipo_filtro"] == "mes_gestion"
    assert data["totales_generales"]["total_ingresos"] == 243
    assert data["totales_generales"]["total_permanencias"] == 486
    assert data["totales_generales"]["total_general"] == 729

    # Nacionales (Bolivia)
    assert data["nacionales"]["pais"] == "Bolivia"
    assert data["nacionales"]["cant_ingresos"] == 100
    assert data["nacionales"]["cant_permanencias"] == 200
    assert data["nacionales"]["total"] == 300
    assert data["nacionales"]["porcentaje_total"] == round((300 / 729 * 100), 2)

    # Extranjeros
    assert data["extranjeros"]["cant_ingresos"] == 143
    assert data["extranjeros"]["cant_permanencias"] == 286
    assert data["extranjeros"]["total"] == 429
    assert data["extranjeros"]["porcentaje_total"] == round((429 / 729 * 100), 2)


@pytest.mark.asyncio
async def test_grafico_torta_filtro_rango_fechas(client: AsyncClient, setup_reportes_data):
    """Verifica el cálculo de la torta filtrando por rango de días exactos."""
    token = setup_reportes_data["admin_token"]

    # Rango del 10 al 12 de septiembre (días de BO, AR, BR)
    response = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionales-extranjeros?fecha_inicio=2026-09-10&fecha_fin=2026-09-12",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["periodo"]["tipo_filtro"] == "rango_fechas"
    # BO en día 10: 100 ing, 200 perm -> 300 tot
    assert data["nacionales"]["cant_ingresos"] == 100
    assert data["nacionales"]["cant_permanencias"] == 200

    # AR en día 11 (40 ing, 80 perm) + BR en día 12 (30 ing, 60 perm) = 70 ing, 140 perm
    assert data["extranjeros"]["cant_ingresos"] == 70
    assert data["extranjeros"]["cant_permanencias"] == 140


# ========================================================
# TESTS: 2. GRÁFICO DE BARRAS (RANKING TOP 10 Y RESTO)
# ========================================================

@pytest.mark.asyncio
async def test_grafico_ranking_nacionalidades_top10_y_resto(client: AsyncClient, setup_reportes_data):
    """
    Verifica que el ranking separe correctamente las 10 nacionalidades con más afluencia
    y proporcione el bloque del 11 en adelante (resto: GB y UY).
    """
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionalidades-ranking?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_paises_con_movimiento"] == 12

    top_10 = data["top_10"]
    assert len(top_10) == 10

    # Puesto 1: Bolivia
    assert top_10[0]["ranking"] == 1
    assert top_10[0]["cod_pais"] == "BO"
    assert top_10[0]["total_afluencia"] == 300

    # Puesto 2: Argentina
    assert top_10[1]["ranking"] == 2
    assert top_10[1]["cod_pais"] == "AR"
    assert top_10[1]["total_afluencia"] == 120

    # Puesto 10: Italia
    assert top_10[9]["ranking"] == 10
    assert top_10[9]["cod_pais"] == "IT"
    assert top_10[9]["total_afluencia"] == 12

    # Resto (posiciones 11 en adelante)
    resto = data["resto"]
    assert len(resto) == 2
    # Puesto 11: Inglaterra (GB)
    assert resto[0]["ranking"] == 11
    assert resto[0]["cod_pais"] == "GB"
    assert resto[0]["total_afluencia"] == 9
    # Puesto 12: Uruguay (UY)
    assert resto[1]["ranking"] == 12
    assert resto[1]["cod_pais"] == "UY"
    assert resto[1]["total_afluencia"] == 6


@pytest.mark.asyncio
async def test_grafico_ranking_filtro_paises_especificos(client: AsyncClient, setup_reportes_data):
    """Verifica que el administrador pueda seleccionar solo los países específicos que desea ver."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionalidades-ranking?mes=septiembre&gestion=2026&codigos_pais=AR&codigos_pais=CL",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_paises_con_movimiento"] == 2
    top = data["top_10"]
    assert len(top) == 2
    assert top[0]["cod_pais"] == "AR"
    assert top[1]["cod_pais"] == "CL"
    assert len(data["resto"]) == 0


# ========================================================
# TESTS: 3. COMPARATIVA PERMANENCIAS VS INGRESOS
# ========================================================

@pytest.mark.asyncio
async def test_permanencias_vs_ingresos_por_pais(client: AsyncClient, setup_reportes_data):
    """Verifica la comparativa de permanencias vs ingresos para un solo país y cálculo del promedio de noches."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/permanencias-vs-ingresos?mes=septiembre&gestion=2026&cod_pais=AR",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["agrupacion"] == "pais"
    assert len(data["series"]) == 1
    item = data["series"][0]
    assert item["codigo"] == "AR"
    assert item["ingresos"] == 40
    assert item["permanencias"] == 80
    assert item["ratio_permanencia_ingreso"] == 2.0  # 80 / 40 = 2.0 noches por huésped


@pytest.mark.asyncio
async def test_permanencias_vs_ingresos_serie_tiempo(client: AsyncClient, setup_reportes_data):
    """Verifica la agrupación cronológica (agrupar_por=tiempo) en días."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/permanencias-vs-ingresos?mes=septiembre&gestion=2026&agrupar_por=tiempo",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["agrupacion"] == "tiempo"
    assert len(data["series"]) == 12
    assert data["series"][0]["etiqueta"] == "Día 10"


# ========================================================
# TESTS: 4. TABLERO EJECUTIVO Y TASA DE OCUPACIÓN
# ========================================================

@pytest.mark.asyncio
async def test_tablero_ejecutivo_kpis_y_tasa_ocupacion(client: AsyncClient, setup_reportes_data):
    """Verifica el cálculo de cobertura, llegadas, pernoctaciones y tasa de ocupación ponderada."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/tablero-ejecutivo?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["establecimientos_registrados"] == 2
    assert data["establecimientos_declarantes"] == 1
    assert data["porcentaje_cobertura_establecimientos"] == 50.0

    assert data["total_ingresos"] == 243
    assert data["total_permanencias"] == 486
    assert data["total_huespedes"] == 729

    # Capacidad: 20 (est1) + 30 (est2) = 50 habitaciones disponibles
    assert data["total_habitaciones_ofertadas"] == 50
    assert data["total_habitaciones_ocupadas"] == 300

    # Septiembre tiene 30 días. Oferta total = 50 habs * 30 días = 1500 hab-noche.
    # Tasa de ocupación = (300 / 1500) * 100 = 20.0%
    assert data["tasa_ocupacion_porcentaje"] == 20.0
    assert data["estadia_media_noches"] == 2.0


# ========================================================
# TESTS: 5. BITÁCORA DE CUMPLIMIENTO INSTITUCIONAL
# ========================================================

@pytest.mark.asyncio
async def test_cumplimiento_declaraciones_al_dia_y_mora(client: AsyncClient, setup_reportes_data):
    """Verifica que identifique correctamente establecimientos al día vs en mora."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/cumplimiento-declaraciones?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_establecimientos"] == 2
    assert data["total_al_dia"] == 1
    assert data["total_pendientes"] == 1
    assert data["porcentaje_cumplimiento"] == 50.0

    # Hotel San Felipe está al día
    est_sanfelipe = next(e for e in data["establecimientos"] if e["nombre_establecimiento"] == "Hotel San Felipe")
    assert est_sanfelipe["cumplimiento_completo"] is True
    assert est_sanfelipe["tiene_estadistica"] is True
    assert est_sanfelipe["tiene_ocupacion"] is True

    # Gran Hotel Oruro está en mora
    est_granhotel = next(e for e in data["establecimientos"] if e["nombre_establecimiento"] == "Gran Hotel Oruro")
    assert est_granhotel["cumplimiento_completo"] is False
    assert est_granhotel["tiene_estadistica"] is False


# ========================================================
# TESTS: 6. EXPORTACIÓN A CSV
# ========================================================

@pytest.mark.asyncio
async def test_exportacion_csv(client: AsyncClient, setup_reportes_data):
    """Verifica la descarga del reporte en formato CSV compatible con Excel."""
    token = setup_reportes_data["admin_token"]

    response = await client.get(
        f"{settings.API_V1_STR}/reportes/exportar/csv?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]

    contenido = response.text
    assert "Hotel San Felipe" in contenido
    assert "Bolivia;BO" in contenido or "Bolivia" in contenido
    assert "Total Afluencia" in contenido


# ========================================================
# TESTS: 7. SEGURIDAD Y AISLAMIENTO MULTI-TENANT
# ========================================================

@pytest.mark.asyncio
async def test_aislamiento_operador_acceso_estadisticas(client: AsyncClient, setup_reportes_data):
    """Un operador solo puede acceder a su propio establecimiento y no puede espiar a otros."""
    op_token = setup_reportes_data["operador_token"]
    est2 = setup_reportes_data["est2"]

    # Consulta legítima (sin especificar ID o con su propio ID): retorna 200 con sus datos
    res_propio = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionales-extranjeros?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {op_token}"}
    )
    assert res_propio.status_code == 200

    # Intento de espiar el establecimiento 2: prohibido 403
    res_ajeno = await client.get(
        f"{settings.API_V1_STR}/reportes/graficos/nacionales-extranjeros?mes=septiembre&gestion=2026&id_establecimiento={est2.id}",
        headers={"Authorization": f"Bearer {op_token}"}
    )
    assert res_ajeno.status_code == 403

    # Intento de ver la bitácora departamental de cumplimiento (Solo admin): prohibido 403
    res_cumplimiento = await client.get(
        f"{settings.API_V1_STR}/reportes/cumplimiento-declaraciones?mes=septiembre&gestion=2026",
        headers={"Authorization": f"Bearer {op_token}"}
    )
    assert res_cumplimiento.status_code == 403
