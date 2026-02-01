import uvicorn
import geopandas as gpd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from io import BytesIO
from PIL import Image
import contextily as ctx

from agent import engine, extract_sql_from_response, generate_query_chain, summary_chain, analyze_satellite_image

app = FastAPI(title="Tactical Sat-Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ScanRequest(BaseModel):
    west: float; south: float; east: float; north: float; zoom: int

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not engine or not generate_query_chain:
        raise HTTPException(status_code=503, detail="Tactical engine offline.")

    last_error = ""
    for attempt in range(3):
        try:
            # Step 1: Generate Query
            raw_response = generate_query_chain.invoke({"question": request.message, "error": last_error})
            query = extract_sql_from_response(raw_response)
            print(f"Generated Query: {query}")
            if not query:
                raise ValueError("LLM generated an empty query.")

            # Step 2: Execute PostGIS Query
            gdf = gpd.read_postgis(text(query), con=engine, geom_col='geom')
            
            # Step 3: Format Response
            if gdf.empty:
                return {"text": "No tactical data found in this sector.", "geojson": None}

            geojson = gdf.to_json()
            # Remove geometries for the text summary to save tokens
            summary_data = gdf.drop(columns=['geom', 'geometry'], errors='ignore').to_string()
            description = summary_chain.invoke({"data_summary": summary_data})

            return {"text": description, "geojson": geojson}

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            last_error = str(e)
            if attempt == 2:
                return {"text": f"SYSTEM_FAILURE: {last_error}", "geojson": None}

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
        
        buff = BytesIO()
        pil_img.save(buff, format="JPEG", quality=85)
        
        # 3. AI Analysis
        description = analyze_satellite_image(buff.getvalue())
        return {"text": description}

    except Exception as e:
        print(f"Scan Error: {e}")
        raise HTTPException(status_code=500, detail="Optical sensors malfunction.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)