from typing import Optional, List, Dict, Any
import uvicorn
import bcrypt
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import uuid
from sqlalchemy import text
from io import BytesIO
from PIL import Image
import contextily as ctx

import agent
from agent import conversations as convo

app = FastAPI(title="Tactical Sat-Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = ""
    image_data: str | None = None
    image_name: str | None = None
    session_id: str | None = None
    resume: str | None = None
    viewport: dict | None = None
    conversation_id: str | None = None


class ConversationCreate(BaseModel):
    operator_id: str


class ConversationRename(BaseModel):
    title: str


class ScanRequest(BaseModel):
    viewport: Optional[dict] = None
    west: Optional[float] = None
    south: Optional[float] = None
    east: Optional[float] = None
    north: Optional[float] = None
    zoom: Optional[int] = 13


class LoginRequest(BaseModel):
    operator_id: str
    access_key: str


def decode_image_payload(image_data: str) -> tuple[bytes, str]:
    """Decode an optional data URL or raw base64 payload into bytes."""
    mime_type = "image/jpeg"
    payload = image_data.strip()

    if payload.startswith("data:") and "," in payload:
        header, payload = payload.split(",", 1)
        if ";" in header:
            mime_type = header[5:header.index(";")]

    try:
        return base64.b64decode(payload, validate=True), mime_type
    except Exception:
        return base64.b64decode(payload), mime_type

# --- ENDPOINTS ---

def _require_db():
    if agent.engine is None:
        raise HTTPException(status_code=503, detail="Database offline: conversazioni non disponibili.")
    return agent.engine, agent.config.schema


@app.post("/api/conversations")
async def create_conversation_endpoint(req: ConversationCreate):
    engine, schema = _require_db()
    return convo.create_conversation(engine, schema, req.operator_id)


@app.get("/api/conversations")
async def list_conversations_endpoint(operator_id: str):
    engine, schema = _require_db()
    return convo.list_conversations(engine, schema, operator_id)


@app.delete("/api/conversations")
async def delete_all_conversations_endpoint(operator_id: str):
    engine, schema = _require_db()
    removed = convo.delete_all_conversations(engine, schema, operator_id)
    return {"status": "ok", "deleted": removed}


@app.get("/api/conversations/{conversation_id}/messages")
async def conversation_messages_endpoint(conversation_id: uuid.UUID):
    engine, schema = _require_db()
    if convo.get_conversation(engine, schema, str(conversation_id)) is None:
        raise HTTPException(status_code=404, detail="Conversazione non trovata.")
    return convo.get_messages(engine, schema, str(conversation_id))


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation_endpoint(conversation_id: uuid.UUID, req: ConversationRename):
    engine, schema = _require_db()
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Titolo vuoto.")
    if not convo.rename_conversation(engine, schema, str(conversation_id), title[:120]):
        raise HTTPException(status_code=404, detail="Conversazione non trovata.")
    return {"status": "ok"}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: uuid.UUID):
    engine, schema = _require_db()
    if not convo.delete_conversation(engine, schema, str(conversation_id)):
        raise HTTPException(status_code=404, detail="Conversazione non trovata.")
    return {"status": "ok"}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        return plain_password == hashed_password
    except Exception:
        return False


@app.post("/api/login")
async def login_endpoint(creds: LoginRequest):
    """
    Verifica le credenziali contro la tabella 'auth' nel DB (con bcrypt hash), con fallback in caso di DB offline.
    """
    FALLBACK_USERS = {
        "OP_ADMIN": ("SIGMA-7", "aegis2026"),
        "CMD_USR_0001": ("OMEGA-9", "tango-down"),
        "CMD_USR_0042": ("ALPHA-3", "falcon99"),
    }

    if agent.engine is None:
        user_info = FALLBACK_USERS.get(creds.operator_id)
        if user_info and user_info[1] == creds.access_key:
            return {
                "status": "AUTHORIZED",
                "clearance": user_info[0],
                "token": "SESSION_OFFLINE_ACTIVE"
            }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CREDENTIALS_INVALID"
        )

    try:
        query = text("SELECT clearance, username, password FROM schema1.auth WHERE username = :username")
        with agent.engine.connect() as conn:
            result = conn.execute(query, {"username": creds.operator_id}).fetchone()

        if result and verify_password(creds.access_key, result[2]):
            return {
                "status": "AUTHORIZED",
                "clearance": result[0],
                "token": "SESSION_eyJhbGciOiJIUzI1NiJ9_ACTIVE"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CREDENTIALS_INVALID"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        user_info = FALLBACK_USERS.get(creds.operator_id)
        if user_info and user_info[1] == creds.access_key:
            return {
                "status": "AUTHORIZED",
                "clearance": user_info[0],
                "token": "SESSION_FALLBACK_ACTIVE"
            }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="AUTH_SYSTEM_FAILURE"
        )

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id or "anonymous"
    image_bytes = None
    mime_type = "image/jpeg"

    if request.image_data:
        try:
            image_bytes, mime_type = decode_image_payload(request.image_data)
        except Exception as e:
            print(f"Vision Error: {e}")
            raise HTTPException(status_code=400, detail="Invalid image payload.")

    conversation_id = request.conversation_id
    persist = conversation_id is not None and agent.engine is not None

    user_text = request.message or request.resume
    if persist and user_text:
        try:
            convo.append_message(agent.engine, agent.config.schema,
                                 conversation_id, "user", user_text)
        except Exception as e:  # noqa: BLE001 - la persistenza non deve bloccare la chat
            print(f"Persist user message failed: {e}")
            persist = False

    try:
        result = agent.run(
            message=request.message,
            session_id=session_id,
            image=image_bytes,
            mime_type=mime_type,
            resume=request.resume,
            viewport=request.viewport,
            conversation_id=conversation_id,
        )
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"text": f"SYSTEM_FAILURE: {e}", "geojson": None, "awaiting_input": False}

    if persist:
        try:
            convo.append_message(agent.engine, agent.config.schema, conversation_id,
                                 "assistant", result.get("text", ""), result.get("geojson"))
            current = convo.get_conversation(agent.engine, agent.config.schema, conversation_id)
            if current and current["title"] == convo.DEFAULT_TITLE and user_text:
                convo.rename_conversation(agent.engine, agent.config.schema, conversation_id,
                                          convo.derive_title(user_text))
        except Exception as e:  # noqa: BLE001
            print(f"Persist assistant message failed: {e}")

    return result


@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    session_id = request.session_id or "anonymous"
    image_bytes = None
    mime_type = "image/jpeg"

    if request.image_data:
        try:
            image_bytes, mime_type = decode_image_payload(request.image_data)
        except Exception as e:
            print(f"Vision Error: {e}")
            raise HTTPException(status_code=400, detail="Invalid image payload.")

    conversation_id = request.conversation_id
    persist = conversation_id is not None and agent.engine is not None

    if persist:
        try:
            curr = convo.get_conversation(agent.engine, agent.config.schema, conversation_id)
            if curr is None:
                convo.create_conversation(agent.engine, agent.config.schema, conversation_id, "OP_ADMIN", "NUOVA CONVERSAZIONE")
        except Exception as e:
            print(f"Ensure conversation row failed: {e}")

    user_text = request.message or request.resume
    if persist and user_text:
        try:
            convo.append_message(agent.engine, agent.config.schema,
                                 conversation_id, "user", user_text)
        except Exception as e:  # noqa: BLE001
            print(f"Persist user message failed: {e}")
            persist = False

    async def event_generator():
        final_result = None
        try:
            async for event in agent.run_stream(
                message=request.message,
                session_id=session_id,
                image=image_bytes,
                mime_type=mime_type,
                resume=request.resume,
                viewport=request.viewport,
                conversation_id=conversation_id,
            ):
                if event.get("type") == "final":
                    final_result = event
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            print(f"Stream Error: {e}")
            err_evt = {"type": "final", "text": f"SYSTEM_FAILURE: {e}", "geojson": None, "awaiting_input": False}
            yield f"data: {json.dumps(err_evt)}\n\n"

        if persist and final_result:
            try:
                convo.append_message(agent.engine, agent.config.schema, conversation_id,
                                     "assistant", final_result.get("text", ""), final_result.get("geojson"))
                current = convo.get_conversation(agent.engine, agent.config.schema, conversation_id)
                if current and current["title"] == convo.DEFAULT_TITLE and user_text:
                    convo.rename_conversation(agent.engine, agent.config.schema, conversation_id,
                                              convo.derive_title(user_text))
            except Exception as e:  # noqa: BLE001
                print(f"Persist assistant message failed: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

class RewindRequest(BaseModel):
    checkpoint_id: str

@app.get("/api/conversations/{conversation_id}/history")
async def get_history_endpoint(conversation_id: str):
    """Retrieve LangGraph checkpoint state history for Time-Travel."""
    history = agent.get_state_history(conversation_id)
    return {"conversation_id": conversation_id, "history": history}

@app.post("/api/conversations/{conversation_id}/rewind")
async def rewind_endpoint(conversation_id: str, req: RewindRequest):
    """Rewind LangGraph state to a previous checkpoint (Time-Travel)."""
    success = agent.rewind_checkpoint(conversation_id, req.checkpoint_id)
    if not success:
        raise HTTPException(status_code=400, detail="Impossibile eseguire lo State Rewind al checkpoint specificato.")
    return {"status": "ok", "rewound_to": req.checkpoint_id}

@app.post("/api/scan")
async def scan_endpoint(request: ScanRequest):
    try:
        from agent.geocode import extract_viewport_bounds
        b = extract_viewport_bounds(request.viewport or {
            "west": request.west, "south": request.south, "east": request.east, "north": request.north
        })
        if not b:
            south, west, north, east = 45.44, 9.16, 45.48, 9.22
        else:
            south, west, north, east = b

        zoom = request.zoom or (request.viewport.get("zoom") if isinstance(request.viewport, dict) else 13) or 13

        # 1. Capture Satellite Imagery
        img, _ = ctx.bounds2img(
            west, south, east, north,
            ll=True, source=ctx.providers.Esri.WorldImagery, zoom=zoom
        )
        
        # 2. Process for Vision Model
        pil_img = Image.fromarray(img).convert('RGB')
        pil_img.thumbnail((1024, 1024))
        
        # Save to buffer
        buff = BytesIO()
        pil_img.save(buff, format="JPEG", quality=85)
        
        # 3. AI Analysis
        description = agent.analyze_satellite_image(agent.vision_llm, buff.getvalue())
        return {"text": description}

    except Exception as e:
        print(f"Scan Error: {e}")
        raise HTTPException(status_code=500, detail="Optical sensors malfunction.")


from fastapi.staticfiles import StaticFiles
import os

models_dir = os.path.join(os.path.dirname(__file__), "models")
if os.path.exists(models_dir):
    app.mount("/models", StaticFiles(directory=models_dir), name="models")

frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)