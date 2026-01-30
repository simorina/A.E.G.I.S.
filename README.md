# 🛡️ A.E.G.I.S. (Advanced Enhanced Geospatial Intelligence System)

**A.E.G.I.S.** is a high-tech geospatial intelligence (GEOINT) platform designed to bridge the gap between human language and spatial databases. It allows military and civilian operators to query geographic data using natural language and perform real-time satellite imagery analysis via AI Vision models.

---

## 🏗️ System Architecture

The project follows a modern **three-tier architecture** with a specialized AI integration layer:

### 1. Frontend (Tactical Web UI)
A "military-grade" interface built with **Tailwind CSS** and **Leaflet.js**.
* **Tactical HUD**: Features a dark-mode interface with CRT-style scanline effects, glowing amber aesthetics, and a crosshair targeting system.
* **Dynamic Mapping**: Renders GeoJSON data returned by the server directly onto the map as interactive layers.
* **Live Intel**: Tracks mouse coordinates and map bounds in real-time for precise situational awareness.

### 2. Backend (FastAPI Core)
The robust Python server (`server.py`) acts as the mission control:
* **Routing**: Manages asynchronous API requests for chat interactions and satellite scans.
* **Data Processing**: Converts raw SQL results into **GeoPandas DataFrames** for seamless GeoJSON serialization.
* **Self-Correction Logic**: Includes an autonomous retry loop that attempts to fix invalid SQL queries up to 3 times by feeding the database error back into the LLM.

### 3. Intelligence Layer (LangChain + Ollama)
* **SQL Agent**: Translates natural language into **PostGIS-enabled PostgreSQL** queries. It identifies relevant tables (e.g., `fermate_metro`) and ensures geometric columns are included.
* **Vision Agent**: Captures map areas, processes them through the **Pillow** library, and utilizes **Ollama Vision Models** (like Moondream or LLaVA) to provide real-time terrain descriptions.

### 4. Data Layer (PostGIS)
* A specialized **PostgreSQL** instance with the **PostGIS** extension to handle complex spatial relationships, coordinates, and geometry data types.

---

## 🚀 Key Features

### 📡 Natural Language to Spatial SQL
Operators can issue verbal-style commands like *"Show me all metro stations on Line 4"* or *"List all infrastructure in the center"*. The system generates the SQL, executes it, and maps the result markers instantly.

### 🛰️ Satellite Intel Scan
A specialized reconnaissance tool:
1.  **Coordinate Capture**: Extracts the current geographic bounds (N, S, E, W) from the map viewport.
2.  **Tile Retrieval**: Downloads high-resolution satellite imagery via **Contextily** (Esri World Imagery).
3.  **AI Reconnaissance**: The image is analyzed by a Vision model to identify urban density, vegetation, or tactical features.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.10+ |
| **API Framework** | FastAPI |
| **Database** | PostgreSQL + PostGIS |
| **AI Orchestration** | LangChain / Ollama |
| **GIS Libraries** | GeoPandas, Contextily, Leaflet.js |
| **Frontend** | HTML5, Tailwind CSS, JavaScript |

---

## 🚦 Getting Started

### Prerequisites
* **Ollama** installed (running an LLM for Text and Vision).
* **PostgreSQL** instance with the **PostGIS** extension.

### Quick Start
1.  **Install Dependencies**:
    ```bash
    pip install fastapi uvicorn geopandas sqlalchemy langchain_ollama contextily pillow
    ```
2.  **Environment Setup**: Configure your credentials in `agent.py`:
    ```python
    DB_USER = "postgres"
    DB_PASS = "your_password"
    DB_HOST = "192.168.1.48"
    ```
3.  **Launch Server**:
    ```bash
    python server.py
    ```
4.  **Engage**: Open `index.html` in a browser to initialize the HUD.

---

> **A.E.G.I.S. // SECURED GEOSPATIAL ACCESS**