import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
from sqlalchemy import text
from io import BytesIO
from PIL import Image
import contextily as ctx

import agent

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

class ScanRequest(BaseModel):
    west: float; south: float; east: float; north: float; zoom: int


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

@app.post("/api/login")
async def login_endpoint(creds: LoginRequest):
    """
    Verifica le credenziali contro la tabella 'agents' nel DB.
    """
    try:
        # Query parametrizzata per sicurezza
        query = text("SELECT * FROM schema1.auth WHERE username = :username AND password = :password")
        
        # Eseguiamo la query usando una connessione dal pool dell'engine
        with agent.engine.connect() as conn:
            # Passiamo i parametri in modo sicuro
            result = conn.execute(query, {"username": creds.operator_id, "password": creds.access_key}).fetchone()

        if result:
            # Login Successo
            return {
                "status": "AUTHORIZED",
                "clearance": result[0],
                "token": "SESSION_eyJhbGciOiJIUzI1NiJ9_ACTIVE" # Fake token per la UI
            }
        else:
            # Login Fallito
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CREDENTIALS_INVALID"
            )
            
    except Exception as e:
        print(f"Login Error: {e}")
        # Se c'è un errore tecnico, ritorniamo comunque 401 per non esporre dettagli
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

    try:
        return agent.run(
            message=request.message,
            session_id=session_id,
            image=image_bytes,
            mime_type=mime_type,
        )
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"text": f"SYSTEM_FAILURE: {e}", "geojson": None}

@app.post("/api/scan")
async def scan_endpoint(request: ScanRequest):
    try:
        # 1. Capture Satellite Imagery
        img, _ = ctx.bounds2img(
            request.west, request.south, request.east, request.north,
            ll=True, source=ctx.providers.Esri.WorldImagery, zoom=request.zoom
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)