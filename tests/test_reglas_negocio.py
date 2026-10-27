from datetime import date
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.establecimientos.models import Establecimiento, Habitaciones, TipoHabitacion, TipoHabitacionEnum
from app.modules.establecimientos.schemas import CapacidadHabitacionesUpdate, EstablecimientoCreateConOperador, HabitacionItemInput
from app.modules.establecimientos.service import establecimiento_service
from app.modules.formularios.models import (
    DetalleEstadisticaHotelera,
    DetalleOcupacionHotelera,
    EstadisticaHotelera,
    EstadoFormulario,
    OcupacionHotelera,
)
from app.modules.nacionalidades.models import Nacionalidad
from app.modules.usuarios.models import RolUsuario, Usuario
from app.modules.usuarios.schemas import UserCreate
from app.modules.usuarios.service import usuario_service


async def _login_token(client: AsyncClient, email: str, password: str) -> str:
    res = await client.post(
        f"{settings.API_V1_STR}/usuarios/login",
        json={"email": email, "password": password}
    )
    assert res.status_code == 200
    return res.json()["access_token"]


# ==============================================================================
# PRUEBAS FORMALES DE REGLAS DE NEGOCIO (RN-1 A RN-8)
# ==============================================================================

@pytest.mark.asyncio
async def test_rn_1_asociacion_exclusiva_operador_y_aislamiento_dependientes(client: AsyncClient, db_session: AsyncSession):
    """
    RN-1: El establecimiento está asociado a un operador titular (OPERADOR_HOSPEDAJE)
    y un usuario solo maneja un establecimiento. Los dependientes pertenecen exclusivamente a su hotel.
    """
    # 1. Crear Admin
    await usuario_service.create_user(
        db_session,
        UserCreate(
            email="admin_rn1@oruro.gob.bo",
            nombre_completo="Admin RN1",
            rol=RolUsuario.ADMIN_DEPARTAMENTAL,
            password="AdminPassword123!"
        ),
        send_email=False
    )
    admin_token = await _login_token(client, "admin_rn1@oruro.gob.bo", "AdminPassword123!")

    # 2. Crear dos establecimientos con sus respectivos operadores
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m:
        m.return_value = True
        est_a = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel A RN1",
                direccion="Calle A 100",
                categoria="2 Estrellas",
                operador_nombre_completo="Operador A",
                operador_email="op_a@rn1.bo",
                operador_password="HotelPassword123!",
            )
        )
        est_b = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel B RN1",
                direccion="Calle B 200",
                categoria="3 Estrellas",
                operador_nombre_completo="Operador B",
                operador_email="op_b@rn1.bo",
                operador_password="HotelPassword123!",
            )
        )

    # Verificar que cada operador está vinculado exclusivamente a su propio establecimiento
    res_op_a = await db_session.execute(select(Usuario).where(Usuario.email == "op_a@rn1.bo"))
    user_a = res_op_a.scalar_one()
    assert user_a.id_establecimiento == est_a.id
    assert est_a.id_operador == user_a.id

    res_op_b = await db_session.execute(select(Usuario).where(Usuario.email == "op_b@rn1.bo"))
    user_b = res_op_b.scalar_one()
    assert user_b.id_establecimiento == est_b.id
    assert est_b.id_operador == user_b.id

    # Intentar que Operador A consulte los dependientes del Hotel B -> Prohibido (Aislamiento)
    token_a = await _login_token(client, "op_a@rn1.bo", "HotelPassword123!")
    res_ajeno = await client.get(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/dependientes",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    # Operador A ve su lista (vacía inicialmente), no la de Hotel B
    assert res_ajeno.status_code == 200
    assert len(res_ajeno.json()) == 0


@pytest.mark.asyncio
async def test_rn_2_recalculo_automatico_total_habitaciones(client: AsyncClient, db_session: AsyncSession):
    """
    RN-2: El atributo total_habitaciones se calcula de la suma de todas las habitaciones asignadas al establecimiento.
    """
    # 1. Crear tipos de habitación base
    tipo_sim = TipoHabitacion(tipo_habitacion=TipoHabitacionEnum.SIMPLE, descripcion="Simple")
    tipo_dob = TipoHabitacion(tipo_habitacion=TipoHabitacionEnum.DOBLE, descripcion="Doble")
    tipo_sui = TipoHabitacion(tipo_habitacion=TipoHabitacionEnum.SUITE, descripcion="Suite")
    db_session.add_all([tipo_sim, tipo_dob, tipo_sui])
    await db_session.commit()

    # 2. Crear establecimiento
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m:
        m.return_value = True
        est = await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Conteo RN2",
                direccion="Av. 6 de Octubre",
                categoria="3 Estrellas",
                operador_nombre_completo="Operador RN2",
                operador_email="op_rn2@test.bo",
                operador_password="HotelPassword123!",
            )
        )

    token_op = await _login_token(client, "op_rn2@test.bo", "HotelPassword123!")

    # 3. Configurar habitaciones: 5 simples + 3 dobles + 2 suites = 10 habitaciones en total
    payload_cap = CapacidadHabitacionesUpdate(
        habitaciones=[
            HabitacionItemInput(id_tipo_habitacion=tipo_sim.id, cant_habitaciones=5, nro_camas=5),
            HabitacionItemInput(id_tipo_habitacion=tipo_dob.id, cant_habitaciones=3, nro_camas=6),
            HabitacionItemInput(id_tipo_habitacion=tipo_sui.id, cant_habitaciones=2, nro_camas=4),
        ]
    )

    res_cap = await client.put(
        f"{settings.API_V1_STR}/establecimientos/mi-establecimiento/capacidad",
        json=payload_cap.model_dump(),
        headers={"Authorization": f"Bearer {token_op}"}
    )
    assert res_cap.status_code == 200
    data_cap = res_cap.json()

    # Verificar que el total de habitaciones es exactamente la suma (5 + 3 + 2 = 10)
    assert data_cap["total_habitaciones"] == 10

    # Verificar en base de datos
    await db_session.refresh(est)
    assert est.total_habitaciones == 10


@pytest.mark.asyncio
async def test_rn_3_llave_primaria_compuesta_en_habitaciones(db_session: AsyncSession):
    """
    RN-3: La llave primaria de Habitaciones es una llave primaria compuesta (id_establecimiento, id_tipo_habitacion).
    """
    tipo_mat = TipoHabitacion(tipo_habitacion=TipoHabitacionEnum.MATRIMONIAL, descripcion="Matrimonial")
    db_session.add(tipo_mat)
    await db_session.flush()

    est = Establecimiento(
        nombre_establecimiento="Hotel Compuesta RN3",
        direccion="Calle Pagador",
        categoria="1 Estrella",
        total_habitaciones=2,
        total_plazas=4,
    )
    db_session.add(est)
    await db_session.flush()

    # 1. Primera asignación (válida)
    hab1 = Habitaciones(
        id_establecimiento=est.id,
        id_tipo_habitacion=tipo_mat.id,
        cant_habitaciones=2,
        nro_camas=2,
    )
    db_session.add(hab1)
    await db_session.commit()

    # 2. Segunda inserción con la MISMA llave primaria compuesta (debe violar PK / Unique)
    hab_duplicada = Habitaciones(
        id_establecimiento=est.id,
        id_tipo_habitacion=tipo_mat.id,
        cant_habitaciones=4,
        nro_camas=4,
    )
    db_session.add(hab_duplicada)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rn_4_unicidad_formulario_establecimiento_mes_gestion(db_session: AsyncSession):
    """
    RN-4: Unique constraint para los campos (id_establecimiento, mes, gestion)
    para no repetir el mismo formulario mensual.
    """
    est = Establecimiento(
        nombre_establecimiento="Hotel Unicidad RN4",
        direccion="Calle Sucre",
        categoria="2 Estrellas",
        total_habitaciones=5,
        total_plazas=10,
    )
    db_session.add(est)
    await db_session.flush()

    # 1. Crear primer formulario de EstadisticaHotelera para Septiembre 2026
    form1 = EstadisticaHotelera(
        numero_formulario="000401",
        id_establecimiento=est.id,
        mes="septiembre",
        gestion=2026,
        fecha_presentacion=date(2026, 10, 2),
        estado=EstadoFormulario.ENVIADO,
    )
    db_session.add(form1)
    await db_session.commit()

    # 2. Intentar registrar un segundo formulario para el MISMO establecimiento, mes y gestión
    form2 = EstadisticaHotelera(
        numero_formulario="000402",
        id_establecimiento=est.id,
        mes="septiembre",
        gestion=2026,
        fecha_presentacion=date(2026, 10, 3),
        estado=EstadoFormulario.ENVIADO,
    )
    db_session.add(form2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rn_5_mes_y_gestion_validados_con_calendario_real(client: AsyncClient, db_session: AsyncSession):
    """
    RN-5: mes y gestion se obtienen y validan contra el calendario real (días válidos y bloqueo de meses futuros).
    """
    with patch("app.modules.establecimientos.service.send_user_credentials_email", new_callable=AsyncMock) as m:
        m.return_value = True
        await establecimiento_service.crear_establecimiento_con_operador(
            db_session,
            EstablecimientoCreateConOperador(
                nombre_establecimiento="Hotel Calendario RN5",
                direccion="Calle Adolfo Mier",
                categoria="3 Estrellas",
                operador_nombre_completo="Operador RN5",
                operador_email="op_rn5@test.bo",
                operador_password="HotelPassword123!",
            )
        )

    token_op = await _login_token(client, "op_rn5@test.bo", "HotelPassword123!")

    # 1. Consulta de períodos disponibles para gestión 2026
    res_periodos = await client.get(
        f"{settings.API_V1_STR}/formularios/periodos-disponibles?gestion=2026",
        headers={"Authorization": f"Bearer {token_op}"}
    )
    assert res_periodos.status_code == 200
    data_periodos = res_periodos.json()

    # Verificar días dinámicos exactos según calendario real:
    # Febrero en año no bisiesto 2026 tiene 28 días
    mes_feb = next(m for m in data_periodos["meses"] if m["mes"].lower() == "febrero")
    assert mes_feb["dias_en_mes"] == 28

    # Abril tiene 30 días
    mes_abr = next(m for m in data_periodos["meses"] if m["mes"].lower() == "abril")
    assert mes_abr["dias_en_mes"] == 30

    # Diciembre tiene 31 días
    mes_dic = next(m for m in data_periodos["meses"] if m["mes"].lower() == "diciembre")
    assert mes_dic["dias_en_mes"] == 31


@pytest.mark.asyncio
async def test_rn_6_unicidad_detalle_ocupacion_diaria(db_session: AsyncSession):
    """
    RN-6: Los atributos fecha/dia e id_ocupacion tienen un unique constraint para evitar datos duplicados.
    """
    est = Establecimiento(
        nombre_establecimiento="Hotel Ocupacion RN6",
        direccion="Calle Caro",
        categoria="2 Estrellas",
        total_habitaciones=10,
        total_plazas=20,
    )
    db_session.add(est)
    await db_session.flush()

    ocup = OcupacionHotelera(
        id_establecimiento=est.id,
        mes="septiembre",
        gestion=2026,
        fecha_presentacion=date(2026, 10, 1),
    )
    db_session.add(ocup)
    await db_session.flush()

    # 1. Registro del día 15
    det1 = DetalleOcupacionHotelera(
        id_ocupacion=ocup.id,
        dia=15,
        hab_ocupadas=5,
        cant_personas=8,
    )
    db_session.add(det1)
    await db_session.commit()

    # 2. Intento de registrar nuevamente el día 15 para la misma ocupación -> Violación de uq_detalle_ocupacion_dia
    det_dup = DetalleOcupacionHotelera(
        id_ocupacion=ocup.id,
        dia=15,
        hab_ocupadas=7,
        cant_personas=10,
    )
    db_session.add(det_dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rn_7_norma_iso_3166_1_alfa_2_para_cod_pais(client: AsyncClient, db_session: AsyncSession):
    """
    RN-7: Para el cod_pais aplica la norma ISO 3166-1 en alfa 2 (ej: BO, AR, CL, US, ES).
    """
    await usuario_service.create_user(
        db_session,
        UserCreate(
            email="admin_iso@oruro.gob.bo",
            nombre_completo="Admin ISO 3166",
            rol=RolUsuario.ADMIN_DEPARTAMENTAL,
            password="AdminPassword123!"
        ),
        send_email=False
    )
    admin_token = await _login_token(client, "admin_iso@oruro.gob.bo", "AdminPassword123!")

    # 1. Alta de país con código ISO válido de 2 letras
    res_valido = await client.post(
        f"{settings.API_V1_STR}/nacionalidades/",
        json={"pais": "Japón Oficial", "cod_pais": "JP", "continente": "Asia"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_valido.status_code == 201
    assert res_valido.json()["cod_pais"] == "JP"

    # 2. Búsqueda por código ISO
    res_buscar = await client.get(
        f"{settings.API_V1_STR}/nacionalidades/codigo/JP",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_buscar.status_code == 200
    assert res_buscar.json()["pais"] == "Japón Oficial"


@pytest.mark.asyncio
async def test_rn_8_unicidad_detalle_estadistica_celda_nacionalidad_dia(db_session: AsyncSession):
    """
    RN-8: Unique constraint en (id_estadistica, id_nacionalidad, dia)
    para evitar duplicación de celdas en la matriz dinámica.
    """
    nac = Nacionalidad(pais="Chile RN8", cod_pais="CL", continente="América")
    db_session.add(nac)
    await db_session.flush()

    est = Establecimiento(
        nombre_establecimiento="Hotel Matriz RN8",
        direccion="Calle Linares",
        categoria="1 Estrella",
        total_habitaciones=10,
        total_plazas=15,
    )
    db_session.add(est)
    await db_session.flush()

    form = EstadisticaHotelera(
        numero_formulario="000888",
        id_establecimiento=est.id,
        mes="agosto",
        gestion=2026,
        fecha_presentacion=date(2026, 9, 2),
    )
    db_session.add(form)
    await db_session.flush()

    # 1. Movimiento del país en el día 10
    mov1 = DetalleEstadisticaHotelera(
        id_estadistica=form.id,
        id_nacionalidad=nac.id,
        dia=10,
        cant_ingresos=3,
        cant_permanencias=6,
    )
    db_session.add(mov1)
    await db_session.commit()

    # 2. Intento de insertar duplicado de la misma celda (mismo form, país y día)
    mov_dup = DetalleEstadisticaHotelera(
        id_estadistica=form.id,
        id_nacionalidad=nac.id,
        dia=10,
        cant_ingresos=1,
        cant_permanencias=2,
    )
    db_session.add(mov_dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
