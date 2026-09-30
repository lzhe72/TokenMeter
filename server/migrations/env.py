from alembic import context
from server.tokenmeter_server.models import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use python -m server.tokenmeter_server.cli migrate with an explicit database URL")
context.configure(connection=connection, target_metadata=Base.metadata, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
