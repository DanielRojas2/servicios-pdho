"""crear_modulo_nacionalidades

Revision ID: b5b9919e37ac
Revises: 736be8cccda6
Create Date: 2026-10-12 10:10:53.353786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5b9919e37ac'
down_revision: Union[str, Sequence[str], None] = '736be8cccda6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAISES_INICIALES = [
    # --- Columnas preimpresas del Formulario Físico PDHO ---
    {"pais": "Bolivia", "cod_pais": "BO", "continente": "América del Sur", "activo": True},
    {"pais": "Argentina", "cod_pais": "AR", "continente": "América del Sur", "activo": True},
    {"pais": "Brasil", "cod_pais": "BR", "continente": "América del Sur", "activo": True},
    {"pais": "Colombia", "cod_pais": "CO", "continente": "América del Sur", "activo": True},
    {"pais": "Chile", "cod_pais": "CL", "continente": "América del Sur", "activo": True},
    {"pais": "Ecuador", "cod_pais": "EC", "continente": "América del Sur", "activo": True},
    {"pais": "Paraguay", "cod_pais": "PY", "continente": "América del Sur", "activo": True},
    {"pais": "Perú", "cod_pais": "PE", "continente": "América del Sur", "activo": True},
    {"pais": "Uruguay", "cod_pais": "UY", "continente": "América del Sur", "activo": True},
    {"pais": "Venezuela", "cod_pais": "VE", "continente": "América del Sur", "activo": True},
    {"pais": "México", "cod_pais": "MX", "continente": "América del Norte", "activo": True},
    {"pais": "Otros America", "cod_pais": "XAM", "continente": "América", "activo": True},
    {"pais": "Canadá", "cod_pais": "CA", "continente": "América del Norte", "activo": True},
    {"pais": "EE.UU.", "cod_pais": "US", "continente": "América del Norte", "activo": True},
    {"pais": "Alemania", "cod_pais": "DE", "continente": "Europa", "activo": True},
    {"pais": "España", "cod_pais": "ES", "continente": "Europa", "activo": True},
    {"pais": "Francia", "cod_pais": "FR", "continente": "Europa", "activo": True},
    {"pais": "Inglaterra", "cod_pais": "GB", "continente": "Europa", "activo": True},
    {"pais": "Italia", "cod_pais": "IT", "continente": "Europa", "activo": True},
    {"pais": "Suiza", "cod_pais": "CH", "continente": "Europa", "activo": True},
    {"pais": "Holanda", "cod_pais": "NL", "continente": "Europa", "activo": True},
    {"pais": "Suecia", "cod_pais": "SE", "continente": "Europa", "activo": True},
    {"pais": "Otros Europa", "cod_pais": "XEU", "continente": "Europa", "activo": True},
    {"pais": "Japón", "cod_pais": "JP", "continente": "Asia", "activo": True},
    {"pais": "Israel", "cod_pais": "IL", "continente": "Asia", "activo": True},
    {"pais": "Otros Asia", "cod_pais": "XAS", "continente": "Asia", "activo": True},
    {"pais": "Oceanía", "cod_pais": "XOC", "continente": "Oceanía", "activo": True},
    {"pais": "Otros", "cod_pais": "XX", "continente": "Otros", "activo": True},

    # --- Cobertura de América (Central, Caribe y adicionales) ---
    {"pais": "Costa Rica", "cod_pais": "CR", "continente": "América Central", "activo": True},
    {"pais": "Cuba", "cod_pais": "CU", "continente": "Caribe", "activo": True},
    {"pais": "Panamá", "cod_pais": "PA", "continente": "América Central", "activo": True},
    {"pais": "República Dominicana", "cod_pais": "DO", "continente": "Caribe", "activo": True},
    {"pais": "Guatemala", "cod_pais": "GT", "continente": "América Central", "activo": True},
    {"pais": "El Salvador", "cod_pais": "SV", "continente": "América Central", "activo": True},
    {"pais": "Honduras", "cod_pais": "HN", "continente": "América Central", "activo": True},
    {"pais": "Nicaragua", "cod_pais": "NI", "continente": "América Central", "activo": True},
    {"pais": "Puerto Rico", "cod_pais": "PR", "continente": "Caribe", "activo": True},
    {"pais": "Jamaica", "cod_pais": "JM", "continente": "Caribe", "activo": True},
    {"pais": "Haití", "cod_pais": "HT", "continente": "Caribe", "activo": True},
    {"pais": "Guyana", "cod_pais": "GY", "continente": "América del Sur", "activo": True},
    {"pais": "Surinam", "cod_pais": "SR", "continente": "América del Sur", "activo": True},

    # --- Cobertura de Europa (Adicionales más comunes) ---
    {"pais": "Portugal", "cod_pais": "PT", "continente": "Europa", "activo": True},
    {"pais": "Bélgica", "cod_pais": "BE", "continente": "Europa", "activo": True},
    {"pais": "Austria", "cod_pais": "AT", "continente": "Europa", "activo": True},
    {"pais": "Noruega", "cod_pais": "NO", "continente": "Europa", "activo": True},
    {"pais": "Dinamarca", "cod_pais": "DK", "continente": "Europa", "activo": True},
    {"pais": "Finlandia", "cod_pais": "FI", "continente": "Europa", "activo": True},
    {"pais": "Irlanda", "cod_pais": "IE", "continente": "Europa", "activo": True},
    {"pais": "Polonia", "cod_pais": "PL", "continente": "Europa", "activo": True},
    {"pais": "República Checa", "cod_pais": "CZ", "continente": "Europa", "activo": True},
    {"pais": "Grecia", "cod_pais": "GR", "continente": "Europa", "activo": True},
    {"pais": "Rusia", "cod_pais": "RU", "continente": "Europa", "activo": True},
    {"pais": "Ucrania", "cod_pais": "UA", "continente": "Europa", "activo": True},
    {"pais": "Rumania", "cod_pais": "RO", "continente": "Europa", "activo": True},
    {"pais": "Croacia", "cod_pais": "HR", "continente": "Europa", "activo": True},
    {"pais": "Hungría", "cod_pais": "HU", "continente": "Europa", "activo": True},
    {"pais": "Turquía", "cod_pais": "TR", "continente": "Europa", "activo": True},

    # --- Cobertura de Asia (Adicionales más comunes) ---
    {"pais": "China", "cod_pais": "CN", "continente": "Asia", "activo": True},
    {"pais": "Corea del Sur", "cod_pais": "KR", "continente": "Asia", "activo": True},
    {"pais": "India", "cod_pais": "IN", "continente": "Asia", "activo": True},
    {"pais": "Taiwán", "cod_pais": "TW", "continente": "Asia", "activo": True},
    {"pais": "Singapur", "cod_pais": "SG", "continente": "Asia", "activo": True},
    {"pais": "Tailandia", "cod_pais": "TH", "continente": "Asia", "activo": True},
    {"pais": "Vietnam", "cod_pais": "VN", "continente": "Asia", "activo": True},
    {"pais": "Malasia", "cod_pais": "MY", "continente": "Asia", "activo": True},
    {"pais": "Indonesia", "cod_pais": "ID", "continente": "Asia", "activo": True},
    {"pais": "Filipinas", "cod_pais": "PH", "continente": "Asia", "activo": True},
    {"pais": "Emiratos Árabes Unidos", "cod_pais": "AE", "continente": "Asia", "activo": True},
    {"pais": "Arabia Saudita", "cod_pais": "SA", "continente": "Asia", "activo": True},
    {"pais": "Qatar", "cod_pais": "QA", "continente": "Asia", "activo": True},

    # --- Cobertura de Oceanía ---
    {"pais": "Australia", "cod_pais": "AU", "continente": "Oceanía", "activo": True},
    {"pais": "Nueva Zelanda", "cod_pais": "NZ", "continente": "Oceanía", "activo": True},
    {"pais": "Fiyi", "cod_pais": "FJ", "continente": "Oceanía", "activo": True},
    {"pais": "Papúa Nueva Guinea", "cod_pais": "PG", "continente": "Oceanía", "activo": True},

    # --- Cobertura de África ---
    {"pais": "Sudáfrica", "cod_pais": "ZA", "continente": "África", "activo": True},
    {"pais": "Egipto", "cod_pais": "EG", "continente": "África", "activo": True},
    {"pais": "Marruecos", "cod_pais": "MA", "continente": "África", "activo": True},
    {"pais": "Nigeria", "cod_pais": "NG", "continente": "África", "activo": True},
    {"pais": "Kenia", "cod_pais": "KE", "continente": "África", "activo": True},
    {"pais": "Senegal", "cod_pais": "SN", "continente": "África", "activo": True},
    {"pais": "Ghana", "cod_pais": "GH", "continente": "África", "activo": True},
    {"pais": "Túnez", "cod_pais": "TN", "continente": "África", "activo": True},
    {"pais": "Argelia", "cod_pais": "DZ", "continente": "África", "activo": True},
    {"pais": "Etiopía", "cod_pais": "ET", "continente": "África", "activo": True},
]


def upgrade() -> None:
    """Creación de tabla nacionalidades y poblamiento con catálogo oficial."""
    nacionalidades_table = op.create_table(
        'nacionalidades',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pais', sa.String(length=100), nullable=False),
        sa.Column('cod_pais', sa.String(length=4), nullable=False),
        sa.Column('continente', sa.String(length=50), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nacionalidades_id'), 'nacionalidades', ['id'], unique=False)
    op.create_index(op.f('ix_nacionalidades_pais'), 'nacionalidades', ['pais'], unique=True)
    op.create_index(op.f('ix_nacionalidades_cod_pais'), 'nacionalidades', ['cod_pais'], unique=True)
    op.create_index(op.f('ix_nacionalidades_continente'), 'nacionalidades', ['continente'], unique=False)

    # Inserción masiva del catálogo de nacionalidades
    op.bulk_insert(nacionalidades_table, PAISES_INICIALES)


def downgrade() -> None:
    """Reversión de la tabla nacionalidades."""
    op.drop_index(op.f('ix_nacionalidades_continente'), table_name='nacionalidades')
    op.drop_index(op.f('ix_nacionalidades_cod_pais'), table_name='nacionalidades')
    op.drop_index(op.f('ix_nacionalidades_pais'), table_name='nacionalidades')
    op.drop_index(op.f('ix_nacionalidades_id'), table_name='nacionalidades')
    op.drop_table('nacionalidades')
