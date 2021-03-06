"""various_updates

Revision ID: 93693ee54c46
Revises: 1772d3afeb49
Create Date: 2019-01-25 17:30:21.121248

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93693ee54c46'
down_revision = '1772d3afeb49'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('arrest', sa.Column('arrest_date', sa.Date(), nullable=True))
    op.drop_column('arrest', 'date')
    op.add_column('arrest_history', sa.Column('arrest_date', sa.Date(), nullable=True))
    op.drop_column('arrest_history', 'date')
    op.add_column('bond', sa.Column('bond_agent', sa.String(length=255), nullable=True))
    op.add_column('bond_history', sa.Column('bond_agent', sa.String(length=255), nullable=True))
    op.add_column('charge', sa.Column('charge_notes', sa.Text(), nullable=True))
    op.add_column('charge_history', sa.Column('charge_notes', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('charge_history', 'charge_notes')
    op.drop_column('charge', 'charge_notes')
    op.drop_column('bond_history', 'bond_agent')
    op.drop_column('bond', 'bond_agent')
    op.add_column('arrest_history', sa.Column('date', sa.DATE(), autoincrement=False, nullable=True))
    op.drop_column('arrest_history', 'arrest_date')
    op.add_column('arrest', sa.Column('date', sa.DATE(), autoincrement=False, nullable=True))
    op.drop_column('arrest', 'arrest_date')
    # ### end Alembic commands ###
