import uvicorn
import geopandas as gpd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
import traceback
import contextily as ctx
from io import BytesIO
from PIL import Image

# Importazioni dall'agente
from agent import engine, extract_sql_from_response, generate_query_chain, summary_chain, analyze_satellite_image

# --- 1. SETUP SERVER FASTAPI ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ScanRequest(BaseModel):
    west: float
    south: float
    east: float
    north: float
    zoom: int

# --- ENDPOINT CHAT ---
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"\n--- Nuova Richiesta Chat: {request.message} ---")
    
    if not engine or not generate_query_chain:
        raise HTTPException(status_code=500, detail="Backend non pronto.")

    max_retries = 3
    current_attempt = 0
    last_error = ""
    gdf = gpd.GeoDataFrame()
    query = ""

    while current_attempt < max_retries:
        print(f"--- Tentativo {current_attempt + 1}/{max_retries} ---")
        
        try:
            inputs = {
                "question": request.message, 
                "error": last_error
            }
            
            raw_llm_response = generate_query_chain.invoke(inputs)
            query = extract_sql_from_response(raw_llm_response)
            
            print(f"Query Generata:\n{query}")

            if not query:
                last_error = "L'LLM non ha generato una query SQL."
                current_attempt += 1
                continue

            # Esecuzione Query
            gdf = gpd.read_postgis(text(query), con=engine, geom_col='geom')
            print(f"Successo! Record trovati: {len(gdf)}")
            break 

        except Exception as e:
            print(f"Errore esecuzione SQL: {e}")
            last_error = str(e)
            current_attempt += 1
            
            if current_attempt == max_retries:
                print("Max tentativi raggiunti.")
                return {"text": f"Errore nel recupero dati: {last_error}", "geojson": None}

    geojson_data = None
    text_response = "Nessun risultato trovato."

    if not gdf.empty:
        try:
            geojson_data = gdf.to_json()
            df_clean = gdf.drop(columns=['geom', 'geometry'], errors='ignore')
            data_string = df_clean.to_string()
            text_response = summary_chain.invoke({"data_summary": data_string})
        except Exception as e:
             text_response = f"Dati recuperati ma errore riassunto: {e}"

    return {
        "text": text_response,
        "geojson": geojson_data
    }

# --- ENDPOINT SCAN (VISION) ---
@app.post("/api/scan")
async def scan_endpoint(request: ScanRequest):
    print(f"\n--- RICHIESTA SCAN SATELLITARE ---")
    # Log dei parametri della buonding box
    print(f"BBox: {request.west:.4f}, {request.south:.4f}, {request.east:.4f}, {request.north:.4f}")

    try:
        # 1. Scarica l'immagine (Tile)
        print("Scaricamento tiles...")
        # Utilizzo contextily per ottenere l'immagine satellitare
        img, ext = ctx.bounds2img(
            request.west, request.south, request.east, request.north,
            ll=True,
            source=ctx.providers.Esri.WorldImagery,
            zoom=request.zoom
        )
        
        # 2. Elaborazione PIL
        from PIL import Image
        pil_img = Image.fromarray(img)
        
        # IMPORTANTE: Conversione RGB per evitare errore RGBA->JPEG
        if pil_img.mode == 'RGBA':
            pil_img = pil_img.convert('RGB')
        
        # Ridimensiona per non sovraccaricare l'LLM
        pil_img.thumbnail((2048, 2048)) 
        
        # 3. Conversione in Bytes (senza salvataggio su disco)
        buff = BytesIO()
        pil_img.save(buff, format="JPEG")
        img_bytes = buff.getvalue()
        
        print("Immagine pronta in memoria. Invio al Vision Model...")

        # 4. Chiama l'agente Vision
        description = analyze_satellite_image(img_bytes)
        
        return {"text": description}

    except Exception as e:
        print(f"ERRORE SCAN: {e}")
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)