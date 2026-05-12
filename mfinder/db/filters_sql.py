import threading
from sqlalchemy import create_engine, text, inspect
from sqlalchemy import Column, TEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from mfinder import DB_URL, LOGGER


BASE = declarative_base()


class Filters(BASE):
    __tablename__ = "filters"
    filters = Column(TEXT, primary_key=True)
    message = Column(TEXT)

    def __init__(self, filters, message):
        self.filters = filters
        self.message = message


def _ensure_filters_schema(engine):
    inspector = inspect(engine)
    if not inspector.has_table("filters"):
        return

    column_names = {col["name"] for col in inspector.get_columns("filters")}
    if "filters" in column_names:
        return

    fallback_columns = ["filter", "keyword", "text", "name"]
    source_column = next((col for col in fallback_columns if col in column_names), None)

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE filters ADD COLUMN filters TEXT"))
        if source_column:
            conn.execute(
                text(f"UPDATE filters SET filters = {source_column} WHERE filters IS NULL")
            )

    LOGGER.warning(
        "Detected legacy filters table schema. Added missing 'filters' column%s.",
        f" and backfilled from '{source_column}'" if source_column else "",
    )


def start() -> scoped_session:
    engine = create_engine(DB_URL, client_encoding="utf8", poolclass=StaticPool)
    BASE.metadata.bind = engine
    BASE.metadata.create_all(engine)
    _ensure_filters_schema(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()
INSERTION_LOCK = threading.RLock()


def _rollback_and_log(err):
    SESSION.rollback()
    LOGGER.error("filters_sql query failed: %s", err)


async def add_filter(filters, message):
    with INSERTION_LOCK:
        try:
            fltr = SESSION.query(Filters).filter(Filters.filters.ilike(filters)).one()
            return bool(fltr)
        except NoResultFound:
            fltr = Filters(filters=filters, message=message)
            SESSION.add(fltr)
            SESSION.commit()
            return True
        except SQLAlchemyError as err:
            _rollback_and_log(err)
            return False


async def is_filter(filters):
    with INSERTION_LOCK:
        try:
            fltr = SESSION.query(Filters).filter(Filters.filters.ilike(filters)).one()
            return fltr
        except NoResultFound:
            return False
        except SQLAlchemyError as err:
            _rollback_and_log(err)
            return False


async def rem_filter(filters):
    with INSERTION_LOCK:
        try:
            fltr = SESSION.query(Filters).filter(Filters.filters.ilike(filters)).one()
            SESSION.delete(fltr)
            SESSION.commit()
            return True
        except NoResultFound:
            return False
        except SQLAlchemyError as err:
            _rollback_and_log(err)
            return False


async def list_filters():
    try:
        fltrs = SESSION.query(Filters.filters).all()
        return [fltr[0] for fltr in fltrs]
    except NoResultFound:
        return False
    except SQLAlchemyError as err:
        _rollback_and_log(err)
        return False
    finally:
        SESSION.close()
