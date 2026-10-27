"""crear_modulo_establecimientos_y_capacidad

Revision ID: 736be8cccda6
Revises: 619fa3904104
Create Date: 2026-10-11 22:10:38.371763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '736be8cccda6'
down_revision: Union[str, Sequence[str], None] = '619fa3904104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear tabla tipos_habitacion
    op.create_table(
        'tipos_habitacion',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tipo_habitacion', sa.String(length=20), nullable=False),
        sa.Column('descripcion', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo_habitacion', name='uq_tipos_habitacion_tipo')
    )
    op.create_index(op.f('ix_tipos_habitacion_id'), 'tipos_habitacion', ['id'], unique=False)
    op.create_index(op.f('ix_tipos_habitacion_tipo_habitacion'), 'tipos_habitacion', ['tipo_habitacion'], unique=True)

    # 2. Poblar tipos de habitación estándar
    tipos_habitacion_table = sa.table(
        'tipos_habitacion',
        sa.column('tipo_habitacion', sa.String),
        sa.column('descripcion', sa.String)
    )
    op.bulk_insert(
        tipos_habitacion_table,
        [
            {'tipo_habitacion': 'simple', 'descripcion': 'Habitación para 1 persona (1 cama simple)'},
            {'tipo_habitacion': 'doble', 'descripcion': 'Habitación para 2 personas (2 camas separadas)'},
            {'tipo_habitacion': 'matrimonial', 'descripcion': 'Habitación con 1 cama de dos plazas / matrimonial'},
            {'tipo_habitacion': 'triple', 'descripcion': 'Habitación para 3 personas'},
            {'tipo_habitacion': 'multiple', 'descripcion': 'Habitación para 4 o más personas'},
            {'tipo_habitacion': 'suite', 'descripcion': 'Habitación tipo suite con comodidades especiales'},
        ]
    )

    # 3. Crear tabla establecimientos
    op.create_table(
        'establecimientos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nombre_establecimiento', sa.String(length=150), nullable=False),
        sa.Column('direccion', sa.String(length=255), nullable=False),
        sa.Column('categoria', sa.String(length=50), nullable=False),
        sa.Column('latitud', sa.Float(), nullable=True),
        sa.Column('longitud', sa.Float(), nullable=True),
        sa.Column('telefono', sa.String(length=50), nullable=True),
        sa.Column('total_habitaciones', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_plazas', sa.Integer(), server_default='0', nullable=False),
        sa.Column('id_operador', sa.Integer(), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('fecha_registro', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['id_operador'], ['usuarios.id'], ondelete='SET NULL', use_alter=True, name='fk_establecimientos_operador'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_operador', name='uq_establecimientos_operador')
    )
    op.create_index(op.f('ix_establecimientos_id'), 'establecimientos', ['id'], unique=False)
    op.create_index(op.f('ix_establecimientos_nombre_establecimiento'), 'establecimientos', ['nombre_establecimiento'], unique=False)

    # 4. Agregar columna id_establecimiento en tabla usuarios
    op.add_column('usuarios', sa.Column('id_establecimiento', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_usuarios_establecimientos',
        'usuarios',
        'establecimientos',
        ['id_establecimiento'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(op.f('ix_usuarios_id_establecimiento'), 'usuarios', ['id_establecimiento'], unique=False)

    # 5. Crear tabla habitaciones con PK compuesta (id_establecimiento, id_tipo_habitacion)
    op.create_table(
        'habitaciones',
        sa.Column('id_establecimiento', sa.Integer(), nullable=False),
        sa.Column('id_tipo_habitacion', sa.Integer(), nullable=False),
        sa.Column('cant_habitaciones', sa.Integer(), server_default='1', nullable=False),
        sa.Column('nro_camas', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['id_establecimiento'], ['establecimientos.id'], ondelete='CASCADE', name='fk_habitaciones_establecimiento'),
        sa.ForeignKeyConstraint(['id_tipo_habitacion'], ['tipos_habitacion.id'], ondelete='CASCADE', name='fk_habitaciones_tipo_habitacion'),
        sa.PrimaryKeyConstraint('id_establecimiento', 'id_tipo_habitacion', name='pk_habitaciones')
    )


def downgrade() -> None:
    op.drop_table('habitaciones')
    op.drop_constraint('fk_usuarios_establecimientos', 'usuarios', type_='foreignkey')
    op.drop_index(op.f('ix_usuarios_id_establecimiento'), table_name='usuarios')
    op.drop_column('usuarios', 'id_establecimiento')
    op.drop_index(op.f('ix_establecimientos_nombre_establecimiento'), table_name='establecimientos')
    op.drop_index(op.f('ix_establecimientos_id'), table_name='establecimientos')
    op.drop_table('establecimientos')
    op.drop_index(op.f('ix_tipos_habitacion_tipo_habitacion'), table_name='tipos_habitacion')
    op.drop_index(op.f('ix_tipos_habitacion_id'), table_name='tipos_habitacion')
    op.drop_table('tipos_habitacion')
