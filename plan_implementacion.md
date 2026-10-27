# Plan de Implementación por Fases: API Plataforma Hotelera Oruro (PDHO)

> **Metodología:** ODD (Outcome-Driven Development) / SDD (Spec-Driven Development)  
> **Arquitectura:** Screaming Architecture (Modular por dominio)  
> **Stack Técnico:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Pydantic v2  
> **Control y Gobernanza:** Aprobación explícita del usuario en cada fase. Sin mutaciones de base de datos ni tests sobre la BD real sin previa autorización.

---

## 1. Tabla de Fases y Estado

| Fase | Descripción | Entregables Clave | Estado |
| :--- | :--- | :--- | :---: |
| **Fase 0** | Configuración del Entorno, Dependencias y Core | `.venv`, `requirements.txt`, `app/core/`, Alembic setup | ✅ Completada |
| **Fase 1** | Autenticación, Seguridad y Gestión de Usuarios | Modelos de usuario/rol, JWT, políticas AGETIC, guards RBAC, envío credenciales por email | ✅ Completada |
| **Fase 2** | Módulo de Establecimientos y Capacidad Instalada | CRUD Establecimientos con Operador titular, Dependientes aislados, Habitaciones, nro_camas, cálculo de total_habitaciones | ✅ Completada |
| **Fase 3** | Módulo de Catálogos y Nacionalidades | Catálogo ISO 3166-1 alfa-2 (RN-7), seeds y endpoints de consulta | ✅ Completada |
| **Fase 4** | Módulo de Formularios Mensuales y Digitalización | EstadisticaHotelera, OcupacionHotelera, Foto a PDF, Matriz Dispersa, Resumen | ✅ Completada |
| **Fase 5** | Módulo Administrativo, Estadísticas y Reportes | Tableros, consolidación regional, filtros dinámicos y exportación | ✅ Completada |
| **Fase 6** | Testing Automatizado Aislado y Hardening de Seguridad | Suite de pruebas en SQLite/Mocks, auditoría PISI/AGETIC | ✅ Completada |
| **Fase 7** | Documentación de Integración para Angular | OpenAPI enriquecido, contratos TypeScript, interceptores y endpoints (Angular 22) | ✅ Completada |

---

## 2. Detalle de Fases de Implementación

### Fase 0: Configuración del Entorno y Arquitectura Base
* **Objetivo:** Preparar la base técnica, aislamiento de entorno y configuración centralizada sin tocar la base de datos real.
* **Actividades:**
  1. Creación del entorno virtual Python `.venv` y su activación en el workspace.
  2. Definición del archivo de dependencias con versiones fijadas (`fastapi`, `uvicorn`, `sqlalchemy>=2.0`, `alembic`, `pydantic>=2.0`, `pydantic-settings`, `asyncpg`/`psycopg2-binary`, `python-jose`, `passlib[bcrypt]`, `pytest`, `httpx`).
  3. Configuración del módulo `app/core/`:
     - `config.py`: Mapeo tipado de variables de entorno desde [.env](file:///c:/Users/Daniel/Desktop/plataforma_pdho/servicios_pdho/.env).
     - `database.py`: Motor de SQLAlchemy 2.0 (`AsyncEngine` o `Engine`), `sessionmaker` y clase base declarativa `Base`.
     - `security.py`: Utilidades criptográficas (hashing Argon2/Bcrypt, generación de tokens).
     - `exceptions.py`: Manejadores globales de errores HTTP y validación estándar.
  4. Inicialización de Alembic para el versionado de esquemas.
  5. Creación del punto de entrada `app/main.py` con health-check y configuración de CORS.
* **Criterio de Aceptación:** Servidor de desarrollo ejecutándose correctamente en local y conexión a base de datos validada sin aplicar migraciones todavía.

---

### Fase 1: Módulo de Autenticación, Seguridad y Usuarios (AGETIC / RBAC)
* **Objetivo:** Proveer un sistema robusto de identidad y permisos según las directrices de AGETIC (PISI, PISLEA, ISO 27001).
* **Actividades:**
  1. Diseño e implementación de modelos `Usuario` y `Rol` (`ADMIN_DEPARTAMENTAL`, `OPERADOR_HOSPEDAJE`).
  2. Implementación de esquemas Pydantic para registro, login, cambio de contraseña y perfiles.
  3. Implementación de servicios de autenticación:
     - Hashing con salting según estándares de seguridad.
     - Tokens JWT con caducidad controlada y refresh token opcional.
     - Políticas de contraseñas robustas (complejidad, longitud, bloqueo por intentos).
  4. Dependencias de seguridad en FastAPI (`get_current_user`, `require_role`).
  5. Pruebas unitarias con mocks de base de datos.
* **Criterio de Aceptación:** Flujo de login, emisión y validación de tokens JWT funcionando, con roles protegidos.

---

### Fase 2: Módulo de Establecimientos y Capacidad Instalada
* **Objetivo:** Permitir el alta de establecimientos con operador titular, autogestión de fichas técnicas, aislamiento de dependientes y configuración de capacidad instalada.
* **Actividades:**
  1. Modelos SQLAlchemy 2.0 y RBAC extendido:
     - Nuevo rol: `DEPENDIENTE_HOSPEDAJE` (personal de apoyo para carga de formularios).
     - `Usuario`: Adición de `id_establecimiento` (FK `establecimientos.id`, `ondelete="SET NULL"`) para vinculación multi-tenant.
     - `Establecimiento`: Datos generales, georreferenciación GPS (`latitud`, `longitud`, `telefono`), `id_operador` titular (FK `usuarios.id`, `use_alter=True`), `total_habitaciones` y `total_plazas`.
     - `TipoHabitacion`: Catálogo de 6 tipos estándar (`simple`, `doble`, `matrimonial`, `triple`, `multiple`, `suite`).
     - `Habitaciones`: Clave primaria compuesta `(id_establecimiento, id_tipo_habitacion)` (**RN-3**), `cant_habitaciones` y campo `nro_camas`.
  2. Reglas de negocio en capa de servicio:
     - **RN-1 (Actualizada):** Cada establecimiento cuenta con un `OPERADOR_HOSPEDAJE` titular y puede albergar múltiples usuarios `DEPENDIENTE_HOSPEDAJE`. Cada operador y dependiente pertenece exclusivamente a su establecimiento.
     - **RN-2 (Actualizada):** `total_habitaciones` se calcula automáticamente como la suma de `cant_habitaciones` de todos los tipos de habitación registrados.
     - **Decisión sobre total_plazas:** Gestionado manualmente por el establecimiento o el administrador departamental.
     - **Aislamiento Multi-Tenant de Dependientes:** Un `OPERADOR_HOSPEDAJE` solo puede consultar, registrar y modificar dependientes de su propio establecimiento, impidiendo el acceso a registros ajenos.
  3. Schemas Pydantic y Endpoints implementados en `app/modules/establecimientos/router.py`:
     - `POST /api/v1/establecimientos/`: Alta simultánea de establecimiento y operador titular con envío automático de credenciales (Admin Departamental).
     - `GET /api/v1/establecimientos/`: Listado consolidado con filtros (Admin Departamental).
     - `GET /api/v1/establecimientos/tipos-habitacion`: Catálogo de tipos de habitaciones.
     - `GET /api/v1/establecimientos/mi-establecimiento`: Consulta de ficha propia (Operador / Dependiente).
     - `PATCH /api/v1/establecimientos/mi-establecimiento`: Actualización de contacto y total_plazas manual (Operador / Dependiente).
     - `PUT /api/v1/establecimientos/mi-establecimiento/capacidad`: Configuración de habitaciones y recálculo automático de `total_habitaciones` (Operador).
     - `GET /api/v1/establecimientos/mi-establecimiento/dependientes`: Listado de dependientes del propio establecimiento (Operador).
     - `POST /api/v1/establecimientos/mi-establecimiento/dependientes`: Alta de dependiente con envío de credenciales (Operador).
     - `PATCH /api/v1/establecimientos/mi-establecimiento/dependientes/{id}`: Habilitación/edición de dependiente propio (Operador).
  4. Suite de pruebas hermética en `tests/test_establecimientos.py` ejecutada en SQLite en memoria (100% aprobada).
  5. Migración de Alembic generada: `736be8cccda6_crear_modulo_establecimientos_y_.py`.
* **Criterio de Aceptación:** Establecimiento y operador creados atómicamente, dependientes aislados con éxito, y capacidad recalculada automáticamente.

---

### Fase 3: Módulo de Catálogos y Nacionalidades
* **Objetivo:** Estandarizar la clasificación de visitantes y procedencias mediante catálogo oficial ISO 3166-1 y formulario departamental.
* **Actividades:**
  1. Modelo `Nacionalidad` (`app/modules/nacionalidades/models.py`) con código ISO 3166-1 alfa-2 (**RN-7**), nombres únicos indexados y clasificación geográfica por continente.
  2. Dataset Semilla y Seeder Idempotente:
     - 28 columnas preimpresas de la planilla física en orden oficial (`Bolivia`, `Argentina`, `Brasil`, `Colombia`, `Chile`, `Ecuador`, `Paraguay`, `Perú`, `Uruguay`, `Venezuela`, `México`, `Otros America`, `Canadá`, `EE.UU.`, `Alemania`, `España`, `Francia`, `Inglaterra`, `Italia`, `Suiza`, `Holanda`, `Suecia`, `Otros Europa`, `Japón`, `Israel`, `Otros Asia`, `Oceanía`, `Otros`).
     - Opciones agregadas explícitas requeridas: `"Otros America"` (`XAM`), `"Otros Europa"` (`XEU`), `"Otros Asia"` (`XAS`) y `"Otros"` (`XX`).
     - Cobertura basta de más de 80 países de América, Europa, Asia, África y Oceanía.
     - Script CLI `scripts/seed_nacionalidades.py` y endpoint administrativo `POST /api/v1/nacionalidades/seed`.
  3. Schemas Pydantic y Endpoints RESTful (`app/modules/nacionalidades/router.py`):
     - `GET /api/v1/nacionalidades/`: Listado con paginación (`skip`, `limit`), búsqueda insensible a mayúsculas (`search`), filtro por `continente` y `solo_activos` (Accesible para Admin, Operador y Dependiente).
     - `GET /api/v1/nacionalidades/{id}`: Detalle por ID (Lectura protegida).
     - `GET /api/v1/nacionalidades/codigo/{cod_pais}`: Búsqueda directa por código de país (ej: `BO`, `XAM`, `US`).
     - `POST /api/v1/nacionalidades/`: Alta manual de nacionalidades (Admin Departamental).
     - `PATCH /api/v1/nacionalidades/{id}`: Modificación de nacionalidades (Admin Departamental).
     - `DELETE /api/v1/nacionalidades/{id}`: Soft-delete / deshabilitación (Admin Departamental).
     - `POST /api/v1/nacionalidades/seed`: Seeder idempotente vía API (Admin Departamental).
  4. Suite de pruebas hermética en `tests/test_nacionalidades.py` sobre SQLite en memoria (100% aprobada).
  5. Migración de Alembic generada: `b5b9919e37ac_crear_modulo_nacionalidades.py` con tabla, índices y bulk_insert semilla listos para PostgreSQL.
* **Criterio de Aceptación:** Catálogo completo de nacionalidades disponible, consultable por código y nombre, e integrado en la aplicación sin mutación de BD real.

---

### Fase 4: Módulo de Formularios Mensuales y Digitalización Inteligente
* **Objetivo:** Digitalizar los instrumentos físicos departamentales ("Estadísticas Hoteleras" y "Ocupación Hotelera") con carga manual directa desde cero, respaldo fotográfico convertido internamente a PDF, calendario real dinámico y persistencia dispersa sin cuellos de botella.
* **Actividades:**
  1. Modelos SQLAlchemy 2.0 y Nomenclatura Oficial:
     - `EstadisticaHotelera` (Reemplaza a `DetalleHuesped`): Formulario físico oficial con número correlativo en rojo (`numero_formulario`, ej: `"000360"`), mes, gestión, empleados permanentes/eventuales, rutas de archivos foto/PDF, estado (`ENVIADO`) y cuadro de resumen matemático integrado. Restricción de unicidad: `(id_establecimiento, mes, gestion)`.
     - `DetalleEstadisticaHotelera`: Matriz dispersa de ingresos y permanencias diarias por país (`id_nacionalidad`, `dia`, `cant_ingresos`, `cant_permanencias`). Persiste únicamente las celdas con movimientos reales > 0.
     - `OcupacionHotelera` (Reemplaza a `OcupacionDiaria`): Formulario de ocupación con total de habitaciones ocupadas por noche y personas alojadas. Restricción de unicidad: `(id_establecimiento, mes, gestion)`.
     - `DetalleOcupacionHotelera`: Detalle diario disperso (`dia`, `hab_ocupadas`, `cant_personas`).
  2. Calendario Real Dinámico y Períodos Permitidos:
     - **Días Dinámicos:** Los días del formulario se calculan con el calendario real (`calendar.monthrange(gestion, mes)`), respetando meses de 28/29 días (febrero bisiesto), 30 días (abril, junio, septiembre, noviembre) y 31 días (enero, marzo, mayo, julio, agosto, octubre, diciembre).
     - **Períodos Declarables:** 
       * Gestión actual (ej. 2026 si estamos en octubre): solo se permite declarar meses concluidos anteriores al mes en curso (enero a septiembre). Mes actual y futuros quedan bloqueados.
       * Gestiones pasadas (ej. 2025): se permite declarar de enero a diciembre.
       * Unicidad: un mes ya declarado para ese establecimiento no puede volver a crearse (se debe usar `PUT` para editar).
  3. Respaldo Digital Liviano (Foto a PDF):
     - Servicio no bloqueante `FileStorageService` que almacena la imagen física del formulario y la transforma internamente a PDF usando `Pillow` en `threadpool` para respaldo legal y ahorro de almacenamiento.
  4. Endpoints RESTful en `app/modules/formularios/router.py`:
     - `GET /api/v1/formularios/periodos-disponibles`: Consulta de meses habilitados, días reales del mes y estado de declaración del establecimiento.
     - `POST /api/v1/formularios/subir-respaldo`: Carga y conversión inmediata de foto a PDF.
     - `POST /api/v1/estadisticas-hoteleras/`: Creación desde cero de Estadísticas Hoteleras.
     - `PUT /api/v1/estadisticas-hoteleras/{id}`: Edición de declaración enviada.
     - `GET /api/v1/estadisticas-hoteleras/`: Listado con filtros (`mes`, `gestion`, paginación).
     - `GET /api/v1/estadisticas-hoteleras/{id}`: Consulta detallada con matriz y resumen.
     - `POST /api/v1/estadisticas-hoteleras/{id}/respaldo`: Adjuntar/actualizar foto y PDF de respaldo.
     - `POST /api/v1/ocupacion-hotelera/`: Creación desde cero de Ocupación Hotelera.
     - `PUT /api/v1/ocupacion-hotelera/{id}`: Edición de ocupación enviada.
     - `GET /api/v1/ocupacion-hotelera/`: Listado con filtros (`mes`, `gestion`, paginación).
     - `GET /api/v1/ocupacion-hotelera/{id}`: Consulta detallada con desglose diario.
     - `POST /api/v1/ocupacion-hotelera/{id}/respaldo`: Adjuntar/actualizar foto y PDF de respaldo.
  5. Suite de pruebas hermética en `tests/test_formularios.py` ejecutada en SQLite en memoria (100% aprobada).
  6. Migración de Alembic aplicada: `c5f0d5126641_crear_modulo_formularios_estadistica_y_.py`.
* **Criterio de Aceptación:** Ambos formularios creados con días dinámicos según calendario real, validación estricta de períodos pasados y unicidad, y respaldo digital foto a PDF.

---

### Fase 5: Módulo Administrativo, Estadísticas y Reportes
* **Objetivo:** Proveer a la administración departamental de Oruro la consolidación estadística y toma de decisiones.
* **Actividades:**
  1. Consultas agregadas de alto rendimiento (SQLAlchemy/SQL nativo):
     - Tasa de ocupación promedio departamental y por categoría.
     - Total de pernoctaciones y llegadas distribuidas por nacionalidad y estacionalidad.
  2. Filtros dinámicos: rango de fechas, mes/gestión, tipo de hospedaje, nacionalidad.
  3. Exportación de datos estructurados para reportes oficiales (JSON analítico, CSV/Excel).
  4. Bitácora de cumplimiento: reporte de hospedajes que presentaron o tienen pendiente su declaración.
* **Criterio de Aceptación:** Métricas agregadas generadas en tiempo real a través de endpoints administrativos protegidos.

---

### Fase 6: Testing Automatizado Aislado y Auditoría de Seguridad
* **Objetivo:** Garantizar la calidad de software cumpliendo estrictamente con la regla de **no tocar la base de datos de producción/desarrollo**.
* **Actividades:**
  1. Configuración de `pytest` con base de datos en memoria (SQLite con emulación o mocks con `unittest.mock` / `factory-boy`).
  2. Pruebas de integración sobre los endpoints mediante `httpx.AsyncClient` o `TestClient`.
  3. Pruebas unitarias de las reglas de negocio (RN-1 a RN-8).
  4. Revisión de seguridad: headers de seguridad, prevención de inyección SQL, validación estricta de payloads.
* **Criterio de Aceptación:** Cobertura de pruebas completa ejecutándose de manera hermética y limpia sin efectos colaterales en PostgreSQL.

---

### Fase 7: Documentación de Integración para Angular
* **Objetivo:** Facilitar el desarrollo del frontend en Angular con especificaciones claras.
* **Actividades:**
  1. Configuración de OpenAPI / Swagger UI enriquecido con descripciones, ejemplos y respuestas de error.
  2. Documentación guía de integración con Angular:
     - Definición de interfaces TypeScript equivalentes a los schemas Pydantic.
     - Configuración de `HttpClient` e interceptor HTTP para Bearer Token.
     - Guía de consumo para el calendario dinámico y formulario de ocupación.
* **Criterio de Aceptación:** Documento técnico completo y Swagger validado para consumo por el equipo de frontend.

---

## 3. Decisiones de Arquitectura Confirmadas por el Usuario

1. **Nomenclatura Entidad Hospedaje:** Estandarizado oficialmente a `Establecimiento` y clave foránea `id_establecimiento`.
2. **Motor de Conexión:** Desarrollo asíncrono con `asyncpg` y `AsyncSession` de SQLAlchemy 2.0.
3. **Fase 0 Aprobada y Completada:** Entorno virtual, dependencias, Alembic async, Core y suite de pruebas aisladas en memoria verificadas.
4. **Fase 1 Aprobada y Completada:** Módulo de usuarios, autenticación JWT, RBAC, servicio de correo SMTP asíncrono y migración en PostgreSQL DB_PDHO ejecutada.
5. **Fase 2 Aprobada y Completada:**
   - Incorporación del rol `DEPENDIENTE_HOSPEDAJE`.
   - Registro atómico de `Establecimiento` y `OPERADOR_HOSPEDAJE` por `ADMIN_DEPARTAMENTAL`.
   - Aislamiento estricto multi-tenant de dependientes por establecimiento.
   - Campo `nro_camas` incluido en `Habitaciones`.
   - Recálculo automático de `total_habitaciones` (RN-2).
   - Gestión manual del campo `total_plazas` por el establecimiento / administrador (según decisión explícita del usuario).
   - Migración de Alembic `736be8cccda6` lista para aplicación en PostgreSQL DB_PDHO previa autorización.
6. **Fase 3 Aprobada y Completada:**
   - Modelo `Nacionalidad` con código ISO 3166-1 alfa-2 (**RN-7**), nombre único y continente.
   - Inclusión exacta de las 28 columnas preimpresas del formulario físico departamental de Oruro.
   - Opciones agregadas explícitas: `"Otros America"` (`XAM`), `"Otros Europa"` (`XEU`), `"Otros Asia"` (`XAS`), `"Otros"` (`XX`) y `"Oceanía"` (`XOC`).
   - Cobertura basta de más de 80 países representativos de cada continente.
   - Seeder automatizado e idempotente mediante endpoint API y script CLI `scripts/seed_nacionalidades.py`.
7. **Fase 4 Aprobada y Completada:**
   - Adopción oficial de nombres: `EstadisticaHotelera` (reemplaza `DetalleHuesped`) y `OcupacionHotelera` (reemplaza `OcupacionDiaria`).
   - Mapeo del identificador correlativo con el número impreso en rojo (ej. `№ 000360`).
   - Mapeo dinámico y enriquecimiento sin duplicación de Secciones A (datos generales) y C (capacidad instalada de habitaciones y plazas) desde el perfil del establecimiento.
   - Matriz dinámica dispersa (`DetalleEstadisticaHotelera` y `DetalleOcupacionHotelera`) que persiste exclusivamente celdas con datos reales (> 0), optimizando la base de datos y evitando sobrecarga de ceros.
   - Cálculo automático y validación estricta del Resumen:
     * `total_nals = r_ingreso_nals + r_permanencia_nals`
     * `total_extr = r_ingreso_extr + r_permanencia_extr`
     * `total_ing = r_ingreso_nals + r_ingreso_extr`
     * `total_perm = r_permanencia_nals + r_permanencia_extr`
     * `total = total_nals + total_extr == total_ing + total_perm`
   - Pipeline de carga de fotos con conversión interna ultrarrápida a PDF (`Pillow` en `threadpool`) sin bloqueos.
   - Flujo *Human-in-the-Loop*: el usuario (operador o dependiente) revisa y edita el borrador antes de confirmar y enviar en limpio.
   - Suite de 19 pruebas herméticas aprobadas al 100% en SQLite en memoria.
   - Migración de Alembic `c5f0d5126641` generada para PostgreSQL DB_PDHO lista para aplicación previa autorización.
8. **Fase 5 Aprobada y Completada:**
   - **Gráfico de Torta (Nacionales vs. Extranjeros):**
     * Desglose completo de llegadas (ingresos), pernoctaciones (permanencias), totales y porcentajes exactos de cuota de mercado.
     * Soporte de filtros optimizados por rango de fechas (días específicos), mes/gestión, año único y rango de gestiones interanuales.
     * Optimización dual: nivel macro con agregaciones ultrarrápidas sobre cabecera y nivel micro con matriz dispersa.
   - **Gráfico de Barras (Ranking de Nacionalidades & Afluencia):**
     * Ranking dinámico ordenado por total de afluencia e ingresos.
     * Separación automática del Top 10 y bloque del 11 en adelante ("resto") con paginación (`skip`, `limit`).
     * Capacidad de filtrado y selección de países específicos por `codigos_pais` o `paises_ids` para análisis enfocado del administrador.
   - **Comparativa Permanencias (Pernoctaciones) vs. Ingresos:**
     * Comparativa para un solo país o conjunto de países seleccionados.
     * Cálculo de la relación de estadía turística media (`ratio_permanencia_ingreso = permanencias / ingresos`).
     * Modos de agrupación por país o series temporales (evolución cronológica por días o meses).
   - **Tablero Ejecutivo y Bitácora de Cumplimiento:**
     * Indicadores departamentales clave: cobertura de establecimientos declarantes, volumen total de visitantes y tasa de ocupación ponderada departamental (`%`).
     * Bitácora institucional para control de cumplimiento mensual (establecimientos al día vs. en mora).
   - **Exportación de Reportes:**
     * Endpoint para exportación en formato CSV estructurado con codificación UTF-8 compatible con Microsoft Excel.
   - **Testing y Aislamiento Multi-Tenant:**
     * Control de acceso estricto RBAC (aislamiento de operadores a su propio establecimiento y privilegios departamentales para el administrador).
     * Suite completa de 10 pruebas automatizadas en `tests/test_reportes.py` ejecutadas al 100% en SQLite en memoria.
9. **Fase 6 Aprobada y Completada:**
   - **Hardening de Seguridad conforme a AGETIC (PISI, PISLEA, ISO 27001):**
     * Inyección en middleware global de 8 cabeceras de seguridad HTTP: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy` y ofuscación de cabecera `Server: PDHO-Secure-API`.
     * Compatibilidad garantizada de CSP con la consola interactiva Swagger UI en `/docs`.
   - **Auditoría Formal de las 8 Reglas de Negocio Oficiales (`tests/test_reglas_negocio.py`):**
     * **RN-1:** Asociación exclusiva entre operador y establecimiento con aislamiento estricto de dependientes.
     * **RN-2:** Recálculo automático del total de habitaciones configuradas.
     * **RN-3:** Clave primaria compuesta en `Habitaciones` `(id_establecimiento, id_tipo_habitacion)`.
     * **RN-4:** Restricción de unicidad para `(id_establecimiento, mes, gestion)` en ambos formularios mensuales.
     * **RN-5:** Validación matemática y cronológica de períodos permitidos según calendario real.
     * **RN-6:** Restricción de unicidad para `(id_ocupacion, dia)` en el detalle diario de ocupación.
     * **RN-7:** Cumplimiento estricto de la norma ISO 3166-1 alfa-2 en códigos de países de procedencia.
     * **RN-8:** Restricción de unicidad en `(id_estadistica, id_nacionalidad, dia)` en la matriz dispersa.
   - **Suite de Seguridad y Mitigación de Vulnerabilidades (`tests/test_seguridad_agetic.py`):**
     * Mitigación de inyecciones SQL en parámetros y filtros.
     * Sanitización contra XSS en cadenas de texto.
     * Criptografía y robustez en tokens JWT (rechazo de firmas manipuladas, expiración y malformación).
     * Políticas de contraseñas robustas conforme a AGETIC (mínimo 8 caracteres, mayúsculas, minúsculas, números y símbolos).
     * Aislamiento multi-tenant entre hospedajes comprobado.
   - **Cobertura de Pruebas Aisladas (Regla 3):**
     * Suite consolidada de 45 pruebas automatizadas ejecutadas al 100% de éxito sobre base de datos SQLite en memoria sin mutar la base de datos PostgreSQL de desarrollo o producción.
10. **Fase 7 Aprobada y Completada:**
    - **Enriquecimiento OpenAPI / Swagger UI:** Metadatos institucionales completos, tags temáticos descriptivos, información de contacto y licencia en `app/main.py`.
    - **Guía de Integración Nativa para Angular 22 (`docs/integracion_angular.md`):**
      * Arquitectura Signals-First, Standalone Components y control flow `@if`, `@for` y `@let`.
      * Configuración global `app.config.ts` con `provideHttpClient` y `withFetch`.
      * Interceptor HTTP funcional `authInterceptor` (`HttpInterceptorFn`) con inyección automática de Bearer Token y manejo centralizado de 401/403.
      * Contratos e interfaces TypeScript tipadas al 100% compatibles con los schemas Pydantic v2 (Auth, Establecimientos, Nacionalidades, Calendario dinámico, Matriz dispersa y Gráficos estadísticos).
      * Guards funcionales `authGuard` y `roleGuard` (`CanActivateFn`).
      * Servicios de dominio reactivos con Signals (`AuthService`, `FormulariosService`, `ReportesService`).
      * Componentes de ejemplo funcionales para el selector de calendario real y carga de respaldo con conversión interna a PDF.


