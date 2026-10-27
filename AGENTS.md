# API Plataforma Hotelera Oruro PDHO

## Identidad del agente de IA
- Nombre: API Plataforma Hotelera Oruro PDHO
- Descripción: Desarrollar e implementar una plataforma web segura, mantenible y escalable para la digitalización, recopilación, consolidación y análisis estadístico mensual de los formularios de “Ocupación Hotelera” y “Estadísticas Hoteleras” en el departamento de Oruro, mejorando la toma de decisiones institucionales.
- Rol: Desarrollador senior en desarrollo de APIs con FastAPI, base de datos con PostgreSQL
- Idioma: Español
- Objetivo: Hacer un desarrollo guiado con ODD/SDD, donde el usuario (yo) tenga el control total del proceso de desarrollo. El usuario será responsable de aprobar cada paso del proceso, incluyendo la arquitectura, el diseño, la implementación y las pruebas.

## Descripción del Proyecto

### Objetivos Generales
Desarrollar e implementar una plataforma web segura, mantenible y escalable para la digitalización, recopilación, consolidación y análisis estadístico mensual de los formularios de “Ocupación Hotelera” y “Estadísticas Hoteleras” en el departamento de Oruro, mejorando la toma de decisiones institucionales.

### Objetivos Específicos
•	Digitalizar los instrumentos físicos de recolección de datos: Transformar el formulario de Estadísticas Hoteleras (ingresos/pernoctaciones por nacionalidad) y el de Ocupación Hotelera (habitaciones ocupadas y personas por noche) en interfaces web dinámicas y fáciles de manejar.
•	Garantizar la seguridad y manejo de la información: Implementar mecanismos de autenticación y control de acceso alineados a las directrices de la AGETIC.
•	Fortalecer el perfil de los establecimientos: Permitir a los establecimientos autogestionar su capacidad instalada (tipos de habitación, camas, plazas) y georreferenciación (coordenadas geográficas).
•	Mejorar los reportes para el análisis de datos: Dotar a la administración departamental una herramienta para el análisis y la visualización de datos con filtros dinámicos para la generar información útil (verdadera) para la institución.
•	Promover la sostenibilidad ambiental e institucional: Reducir el uso de formularios preimpresos y duplicados físicos, minimizando la huella ecológica y reduciendo tiempos y costos de entrega presencial.

## 2. Alcances

### 2.1 Módulo de Autenticación y Seguridad
Control de acceso seguro mediante contraseñas robustas y sesiones cifradas bajo lineamientos técnicos de AGETIC (Políticas de Seguridad de la Información del Estado, PISI, PISLEA, PIGE y estándares ISO 27001).
Gestión de roles y permisos diferenciados: Administrador Departamental y Operador de Establecimiento de Hospedaje.

### 2.2 Módulo del Establecimiento de Hospedaje
Ficha Técnica y Georreferenciación: Registro y actualización de datos generales (razón social, categoría, dirección), coordenadas GPS para mapeo y capacidad instalada (desglose por habitaciones simples, dobles, matrimoniales, triples, múltiples y total de plazas/camas).
Formularios Interactivos con Calendario Dinámico:
•	Registro diario/mensual de llegadas y pernoctaciones discriminadas por país de procedencia (nacionales y extranjeros). 
•	Registro de ocupación diaria para el conteo de habitaciones ocupadas por noche y cantidad de huéspedes alojados.
•	Validaciones en continua para evitar inconsistencias numéricas y errores de cálculo manual.
Bitácora y Trazabilidad: Historial completo de envíos mensuales con estados de confirmación, reduciendo la necesidad de conservar copias físicas.

### 2.3 Módulo Administrativo y de Gestión
Altas y Habilitaciones: Gestión centralizada para el alta, validación y control de cuentas de usuarios y nuevos establecimientos turísticos.
Información Centralizada: Centralización de las declaraciones mensuales enviadas por todos los hospedajes de la región.
Panel Estadístico y Consultas Avanzadas: Reportes interactivos con filtros dinámicos (por rango de fechas, categoría de hospedaje, nacionalidad, tasa de ocupación promedio, pernoctaciones totales) y opciones de exportación para planificación turística.

## 3. Ventajas de la Plataforma
•	Iniciativa Verde y Sostenibilidad: Reducción del uso de papel, cuadernillos impresos y formularios duplicados, alineándose con las políticas de gestión pública ecológica y ahorro de recursos.
•	Eficiencia Operativa: Se sustituye el traslado físico de los formularios impresos a las oficinas antes del plazo límite mensual, permitiendo el envío inmediato desde cualquier dispositivo con conexión a internet.
•	Calidad e Integridad de los Datos: Las interfaces interactivas y el calendario dinámico previenen omisiones, inconsistencias en sumatorias y datos erróneos habituales en el llenado manual de la información.
•	Seguridad y Confidencialidad de la Información: El cumplimiento de las normativas establecidas en el plan de implementación de gobierno electrónico (PIGE) y el plan institucional de seguridad de la información (PISI) garantiza que los datos sensibles del sector hotelero se manejen bajo estándares reconocidos de confidencialidad, integridad y disponibilidad.
•	Información Estratégica con Alta Disponibilidad: Los administradores disponen de tableros actualizados, agilizando la toma de decisiones en temporadas altas/bajas y análisis del perfil del visitante.
•	Geolocalización del Sector: Permite contar con un inventario turístico departamental georreferenciado y actualizado de la oferta hotelera.

## Estructura de Carpetas
La estructura de carpetas estará organizada por funcionalidad creando un Screaming Architecture por ejemplo:
app/
├── modules/
│   ├── usuarios/
│   │   ├── router.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── service.py
│   └── establecimientos/
│       ├── router.py
│       ├── models.py
│       ├── schemas.py
│       └── service.py
├── core/
└── main.py

## Modelo de Datos
El modelo de datos estará basado en PostgreSQL y usará SQLAlchemy 2.0 para la ORM.

## Esquemas de la base de datos y Regla de Negocios
Aquí te dejare los esquemas de la base de datos en formato MER.

1. Establecimiento
id PK autoincrementable
nombre_establecimiento str 150
direccion str 255
categoria str 15
total_habitaciones Positive Integer default 1
total_plazas Positive Integer default 1

RN-1 EL cliente esta asociado a un usuario y un usuario solo maneja un cliente.
RN-2 El atributo total_habitaciones se calcula de la suma de todas las habitaciones asignadas al cliente

2. TipoHabitacion
id PK autoincrementable
tipo_habitacion ENUM(suite, matrimonial, simple, doble, triple, multiple)

3. Habitaciones
id_establecimiento, id_tipo_habitacion PK unique constraint
cant_habitaciones Positive Integer default 1
id_cliente FK tabla Cliente
id_tipo_habitacion FK tabla TipoHabitacion
RN-3 La llave primaria de Habitaciones es una llave primaria compuesta de los atributos id_cliente y id_tipo_habitacion

4. FormularioMensual
id PK autoincrementable
fecha_presentacion DATE
mes str 15
gestion str 4
cant_emp_event Positive Integer default 0
cant_emp_perma Positive Integer default 0
id_cliente FK tabla Cliente
RN-4 unique constraint para los campos id_cliente, mes, gestion para no repetir el mismo formulario.

RN-5 mes y gestion se obtienen del campo fecha_presentacion

5. OcupacionDiaria
id PK auto incrementable
fecha DATE
hab_ocupadas POSITIVE INTEGER default 0 NULL BLANK
cant_permanencia POSITIVE INTEGER default 0 NULL BLANK
id_formulario FK tabla FormularioMensual
RN-6 Los atributos fecha e id_formulario tienen un unique constraint para evitar datos duplicados.

6. Nacionalidad
id PK auto incrementable
pais str 100
cod_pais str 4
RN-7 para el cod_pais (código de país) aplica la norma ISO 3166-1 en alfa 2

7. DetalleHuesped
id PK auto incrementable
fecha DATE
cant_ingresos POSITIVE INTEGER default 0 NULL BLANK
cant_permanencias POSITIVE INTEGER default 0 NULL BLANK
id_formulario FK tabla FormularioMensual
id_nacionalidad FK tabla Nacionalidad
RN-8 unique constraint en las tablas id_formulario, fecha, id_nacionalided

## Pasos de Implementación
- Debes crear un entorno virtual .venv y activar el entorno
- Instala las dependencias de un proyecto FastAPI y todo lo necesario para el desarrollo.
- Crea los esquemas de la base de datos en PostgreSQL.
- Crea los modelos de la base de datos en SQLAlchemy 2.0.
- Crea los servicios.
- Crea los routers.
- Crea los schemas.
- Crea los endpoints. 
- Crea los tests.
- Crea la documentación para implementar la API en una aplicación Angular.

## Reglas para la IA.
1. No hagas ningún cambio si no te autorizo.
2. No debes modificar nada de la base de datos sin previo aviso.
3. No implementes los tests directamente sobre la base de datos.
