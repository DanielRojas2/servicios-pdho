from fastapi.staticfiles import StaticFiles
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

tags_metadata = [
    {
        "name": "Autenticación y Usuarios",
        "description": "Control de acceso, gestión de sesiones JWT, roles RBAC y envío de credenciales conforme a directrices de AGETIC.",
    },
    {
        "name": "Establecimientos y Capacidad Instalada",
        "description": "Ficha técnica, georreferenciación GPS, categorización, capacidad instalada de habitaciones/plazas y gestión aislada de dependientes.",
    },
    {
        "name": "Catálogo de Nacionalidades",
        "description": "Estandarización de procedencias según norma ISO 3166-1 alfa-2 y columnas preimpresas del formulario oficial.",
    },
    {
        "name": "Formularios Hoteleros (Digitalización y Operativa)",
        "description": "Carga de Estadísticas Hoteleras y Ocupación Hotelera, calendario dinámico real, matriz dispersa y conversión de fotos a PDF.",
    },
    {
        "name": "Módulo Administrativo y Reportes Estadísticos",
        "description": "Tableros ejecutivos, gráficos estadísticos dinámicos (torta, ranking de barras, permanencias vs ingresos), bitácora de cumplimiento y exportación CSV.",
    },
    {
        "name": "Salud",
        "description": "Verificación de disponibilidad y health-check del servicio.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "API de alto rendimiento para la digitalización, recopilación, consolidación y análisis "
        "estadístico mensual de ocupación y estadísticas hoteleras en Oruro (PDHO). Desarrollada "
        "con arquitectura modular y lineamientos AGETIC.\n\n"
        "### 📚 Recursos de Documentación y Especificación:\n"
        "- 📖 **ReDoc UI:** [/api/v1/redoc](/api/v1/redoc)\n"
        "- ⚡ **Swagger UI interactivo:** [/api/v1/docs](/api/v1/docs)\n"
        "- 📥 **[Descargar Especificación OpenAPI YAML (openapi.yaml)](/api/v1/openapi.yaml/download)**\n"
        "- 📄 **[Ver Especificación OpenAPI YAML en el navegador](/api/v1/openapi.yaml)**\n"
        "- 🌐 **[Ver Especificación OpenAPI JSON](/api/v1/openapi.json)**"
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    openapi_tags=tags_metadata,
    contact={
        "name": "Unidad de Turismo y Gobernanza Digital - Oruro",
        "url": "https://oruro.gob.bo",
    },
    license_info={
        "name": "Gobierno Autónomo Departamental de Oruro",
    },
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS if settings.BACKEND_CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """
    Middleware de hardening de seguridad conforme a lineamientos AGETIC (PISI / ISO 27001).
    Inyecta cabeceras HTTP de protección contra ataques web comunes en todas las respuestas.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Server"] = "PDHO-Secure-API"

    # CSP para endpoints de la API, compatible con Swagger UI y ReDoc
    if app.docs_url and request.url.path in [app.docs_url, app.redoc_url]:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdn.redoc.ly; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com;"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'"

    return response


import yaml
from fastapi import Response

from app.modules.establecimientos.router import router as establecimientos_router
from app.modules.formularios.router import router as formularios_router
from app.modules.nacionalidades.router import router as nacionalidades_router
from app.modules.reportes.router import router as reportes_router
from app.modules.usuarios.router import router as usuarios_router

app.include_router(usuarios_router, prefix=settings.API_V1_STR)
app.include_router(establecimientos_router, prefix=settings.API_V1_STR)
app.include_router(nacionalidades_router, prefix=settings.API_V1_STR)
app.include_router(formularios_router, prefix=settings.API_V1_STR)
app.include_router(reportes_router, prefix=settings.API_V1_STR)

if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get(
    f"{settings.API_V1_STR}/openapi.yaml",
    tags=["Documentación OpenAPI"],
    summary="Especificación OpenAPI en formato YAML",
)
async def get_openapi_yaml():
    """
    Retorna la especificación OpenAPI 3.1 completa en formato YAML con todos los esquemas,
    rutas, request bodies, respuestas y parámetros para consumo del equipo de frontend.
    """
    schema = app.openapi()
    yaml_content = yaml.dump(schema, sort_keys=False, allow_unicode=True)
    return Response(content=yaml_content, media_type="text/yaml; charset=utf-8")


@app.get(
    f"{settings.API_V1_STR}/openapi.yaml/download",
    tags=["Documentación OpenAPI"],
    summary="Descargar archivo openapi.yaml",
)
async def download_openapi_yaml():
    """
    Descarga directamente el archivo 'openapi_pdho.yaml' para compartirlo o importarlo
    en Postman, Swagger Editor, Insomnia o herramientas de generación de código en Angular.
    """
    schema = app.openapi()
    yaml_content = yaml.dump(schema, sort_keys=False, allow_unicode=True)
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": "attachment; filename=openapi_pdho.yaml"
        }
    )


@app.get(f"{settings.API_V1_STR}/health", tags=["Salud"])
async def health_check():
    """Endpoint de verificación de estado y disponibilidad del servicio."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0"
    }
