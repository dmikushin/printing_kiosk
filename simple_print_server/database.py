
# http://flask.pocoo.org/docs/0.11/patterns/sqlalchemy/

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def _migrate():
    """Idempotent in-place schema migrations for sqlite.

    Adds columns introduced after the original schema. ``CREATE TABLE`` only
    creates a table if it does not already exist, so column additions on an
    existing table need a separate ALTER step. SQLite supports
    ``ALTER TABLE ... ADD COLUMN`` from version 3.2.
    """
    try:
        cols = engine.execute("PRAGMA table_info('printedfiles')").fetchall()
    except Exception:
        return  # table doesn't exist yet; create_all() will handle it
    existing = {row[1] for row in cols}  # row[1] is column name
    if 'pages' not in existing:
        engine.execute("ALTER TABLE printedfiles ADD COLUMN pages VARCHAR(120)")


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import simple_print_server.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate()
