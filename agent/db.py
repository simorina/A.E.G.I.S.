import logging
from typing import List

import geopandas as gpd
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase

log = logging.getLogger(__name__)


def make_engine(db_uri: str):
    return create_engine(db_uri)


def make_sql_database(db_uri: str, schema: str) -> SQLDatabase:
    return SQLDatabase.from_uri(db_uri, schema=schema)


def get_table_info(sql_db: SQLDatabase) -> str:
    return sql_db.get_table_info()


def readonly_preamble(statement_timeout_ms: int) -> List[str]:
    """Statement di sessione che forzano sola-lettura e timeout (int coerciti)."""
    return [
        f"SET statement_timeout = {int(statement_timeout_ms)}",
        "SET default_transaction_read_only = on",
    ]


def execute_readonly(engine, sql: str, statement_timeout_ms: int, geom_col: str = "geom"):
    """Esegue una SELECT in una connessione forzata read-only e ritorna un GeoDataFrame."""
    with engine.connect() as conn:
        try:
            for stmt in readonly_preamble(statement_timeout_ms):
                conn.execute(text(stmt))
            # I SET sono session-scoped ma `default_transaction_read_only` vale solo per le
            # transazioni che INIZIANO dopo. SQLAlchemy ha gia' aperto la tx (autobegin) al
            # primo execute: la chiudiamo col commit cosi' la SELECT seguente eredita il
            # read-only. Senza questo commit lo Strato 2 non rifiuta le scritture.
            conn.commit()
            gdf = gpd.read_postgis(text(sql), con=conn, geom_col=geom_col)
            log.info("execute_readonly: %d rows", len(gdf))
            return gdf
        finally:
            try:
                conn.execute(text("RESET default_transaction_read_only; RESET statement_timeout;"))
                conn.commit()
            except Exception:
                pass
