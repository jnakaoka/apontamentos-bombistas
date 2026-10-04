"""Initial independent schema."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.Integer,primary_key=True),sa.Column('name',sa.String(150),nullable=False),sa.Column('email',sa.String(254),unique=True,nullable=False),sa.Column('password',sa.Text,nullable=False),sa.Column('role',sa.String(20),nullable=False),sa.Column('active',sa.Boolean,nullable=False))
    op.create_table('catalog',sa.Column('id',sa.Integer,primary_key=True),sa.Column('kind',sa.String(20),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('address',sa.String(500),nullable=False),sa.Column('client_id',sa.Integer,sa.ForeignKey('catalog.id')),sa.Column('active',sa.Boolean,nullable=False))
    op.create_table('entries',sa.Column('id',sa.Integer,primary_key=True),sa.Column('operator_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),*[sa.Column(k,sa.Integer,sa.ForeignKey('catalog.id'),nullable=k=='helper_id') for k in ['client_id','site_id','pump_id','helper_id']],sa.Column('start',sa.DateTime(timezone=True),nullable=False),sa.Column('end',sa.DateTime(timezone=True),nullable=False),sa.Column('pause_minutes',sa.Integer,nullable=False),sa.Column('concrete_m3',sa.Numeric(12,2),nullable=False),sa.Column('line_m',sa.Numeric(12,2),nullable=False),sa.Column('origin',sa.String(500),nullable=False),sa.Column('destination',sa.String(500),nullable=False),sa.Column('notes',sa.Text,nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('revision',sa.Integer,nullable=False),sa.Column('review_note',sa.Text,nullable=False))
    op.create_index('ix_entries_operator_start','entries',['operator_id','start'])
    op.create_table('audit',sa.Column('id',sa.Integer,primary_key=True),sa.Column('entry_id',sa.Integer,sa.ForeignKey('entries.id'),nullable=False),sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.Text,nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))
def downgrade():
    for table in ['audit','entries','catalog','users']: op.drop_table(table)
