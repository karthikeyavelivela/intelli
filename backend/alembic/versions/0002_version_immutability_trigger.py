"""DB-level immutability for metric_versions (PostgreSQL). SQLite relies on the ORM guard + a trigger too.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION im_block_version_mutation() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'metric_versions rows are immutable';
            END; $$ LANGUAGE plpgsql;
            """
        )
        op.execute("CREATE TRIGGER trg_metric_versions_immutable BEFORE UPDATE OR DELETE ON metric_versions FOR EACH ROW EXECUTE FUNCTION im_block_version_mutation();")
    elif bind.dialect.name == "sqlite":
        op.execute("CREATE TRIGGER trg_metric_versions_no_update BEFORE UPDATE ON metric_versions BEGIN SELECT RAISE(ABORT, 'metric_versions rows are immutable'); END;")
        op.execute("CREATE TRIGGER trg_metric_versions_no_delete BEFORE DELETE ON metric_versions BEGIN SELECT RAISE(ABORT, 'metric_versions rows are immutable'); END;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_metric_versions_immutable ON metric_versions;")
        op.execute("DROP FUNCTION IF EXISTS im_block_version_mutation();")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_metric_versions_no_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_metric_versions_no_delete;")
