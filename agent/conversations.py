import logging
import uuid

from sqlalchemy import text

log = logging.getLogger(__name__)

DEFAULT_TITLE = "NUOVA CONVERSAZIONE"


def derive_title(text_value: str, max_len: int = 40) -> str:
    """Titolo dalla prima riga del messaggio, normalizzata e troncata."""
    first_line = (text_value or "").strip().splitlines()[0] if (text_value or "").strip() else ""
    cleaned = " ".join(first_line.split())
    if not cleaned:
        return DEFAULT_TITLE
    if len(cleaned) > max_len:
        return cleaned[:max_len] + "…"
    return cleaned


def ensure_schema(engine, schema: str) -> None:
    """Crea le tabelle applicative se assenti (idempotente)."""
    ddl = [
        f"""CREATE TABLE IF NOT EXISTS {schema}.conversations (
                id          UUID PRIMARY KEY,
                operator_id VARCHAR(64)  NOT NULL REFERENCES {schema}.auth(username) ON DELETE CASCADE,
                title       VARCHAR(120) NOT NULL,
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now())""",
        f"""CREATE INDEX IF NOT EXISTS conversations_operator_idx
                ON {schema}.conversations (operator_id, updated_at DESC)""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.messages (
                id              BIGSERIAL PRIMARY KEY,
                conversation_id UUID NOT NULL
                    REFERENCES {schema}.conversations(id) ON DELETE CASCADE,
                role            VARCHAR(16) NOT NULL,
                content         TEXT NOT NULL,
                geojson         TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now())""",
        f"""CREATE INDEX IF NOT EXISTS messages_conversation_idx
                ON {schema}.messages (conversation_id, id)""",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))


def _row_to_conversation(row) -> dict:
    return {
        "id": str(row.id),
        "operator_id": row.operator_id,
        "title": row.title,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def create_conversation(engine, schema: str, operator_id: str, title: str = DEFAULT_TITLE) -> dict:
    new_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        row = conn.execute(text(
            f"""INSERT INTO {schema}.conversations (id, operator_id, title)
                VALUES (:id, :operator_id, :title)
                RETURNING id, operator_id, title, created_at, updated_at"""),
            {"id": new_id, "operator_id": operator_id, "title": title}).one()
        return _row_to_conversation(row)


def list_conversations(engine, schema: str, operator_id: str) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"""SELECT id, operator_id, title, created_at, updated_at
                FROM {schema}.conversations
                WHERE operator_id = :operator_id
                ORDER BY updated_at DESC"""),
            {"operator_id": operator_id}).all()
    return [_row_to_conversation(r) for r in rows]


def get_conversation(engine, schema: str, conversation_id: str):
    with engine.connect() as conn:
        row = conn.execute(text(
            f"""SELECT id, operator_id, title, created_at, updated_at
                FROM {schema}.conversations WHERE id = :id"""),
            {"id": conversation_id}).first()
    return _row_to_conversation(row) if row else None


def get_messages(engine, schema: str, conversation_id: str) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"""SELECT role, content, geojson, created_at
                FROM {schema}.messages
                WHERE conversation_id = :cid ORDER BY id"""),
            {"cid": conversation_id}).all()
    return [{"role": r.role, "content": r.content, "geojson": r.geojson,
             "created_at": r.created_at.isoformat()} for r in rows]


def append_message(engine, schema: str, conversation_id: str, role: str,
                   content: str, geojson=None) -> None:
    with engine.begin() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        conn.execute(text(
            f"""INSERT INTO {schema}.messages (conversation_id, role, content, geojson)
                VALUES (:cid, :role, :content, :geojson)"""),
            {"cid": conversation_id, "role": role, "content": content, "geojson": geojson})
        conn.execute(text(
            f"UPDATE {schema}.conversations SET updated_at = now() WHERE id = :cid"),
            {"cid": conversation_id})


def rename_conversation(engine, schema: str, conversation_id: str, title: str) -> bool:
    with engine.begin() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        result = conn.execute(text(
            f"UPDATE {schema}.conversations SET title = :title, updated_at = now() WHERE id = :cid"),
            {"title": title, "cid": conversation_id})
    return result.rowcount > 0


def delete_all_conversations(engine, schema: str, operator_id: str) -> int:
    """Elimina TUTTE le conversazioni di un operatore (messaggi in cascade).
    Ritorna quante ne sono state eliminate."""
    with engine.begin() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        result = conn.execute(text(
            f"DELETE FROM {schema}.conversations WHERE operator_id = :operator_id"),
            {"operator_id": operator_id})
    return result.rowcount


def delete_conversation(engine, schema: str, conversation_id: str) -> bool:
    with engine.begin() as conn:
        conn.execute(text("SET default_transaction_read_only = off"))
        result = conn.execute(text(
            f"DELETE FROM {schema}.conversations WHERE id = :cid"), {"cid": conversation_id})
    return result.rowcount > 0
