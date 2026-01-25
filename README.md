# A.E.G.I.S. // Geospatial Intelligence Agent

![Status](https://img.shields.io/badge/STATUS-OPERATIONAL-brightgreen) ![Security](https://img.shields.io/badge/CLEARANCE-TOP%20SECRET-red) ![Tech](https://img.shields.io/badge/TECH-AI%20%7C%20POSTGIS-blue)

> **"Eyes in the sky, boots on the ground."**

**A.E.G.I.S.** (Autonomous Entity for Geospatial Intelligence & Surveillance) is an advanced GEOINT system powered by Artificial Intelligence. It bridges the gap between Large Language Models (LLMs), spatial databases (PostGIS), and computer vision to provide real-time tactical analysis of urban environments.

The interface is engineered to simulate a military **Tactical Ops Center**, granting operators direct control over vector data querying and satellite optical reconnaissance.

---

## 🎯 Key Features

### 1. 💬 Chat-to-SQL (Tactical Query)
Query the geospatial database using natural language.
* **Engine:** LangChain + Ollama (DeepSeek/Llama3).
* **Capability:** Converts requests like *"Identify all railway stations within the city center"* into complex PostGIS SQL queries.
* **Output:** Generates GeoJSON data rendered dynamically on the tactical map.

### 2. 🛰️ Optical Recon (SCAN Mode)
Visual terrain analysis via satellite imagery.
* **Engine:** Contextily + Ollama (LLaVA/Vision Model).
* **Capability:** Downloads high-resolution satellite tiles of the current viewport and transmits them to a Multimodal AI.
* **Output:** A concise, military-style report covering urban density, critical infrastructure, and terrain features.

### 3. 🖥️ "War Room" Interface
* Interactive map with hybrid satellite/street layers.
* Futuristic/Military aesthetic (Tailwind CSS).
* Real-time visual feedback (System Loaders, HUD, Event Logs).

---

## 🛠️ Tech Stack

* **Backend:** Python 3.10+, FastAPI.
* **Database:** PostgreSQL + PostGIS.
* **AI/LLM:** Ollama (Local), LangChain.
* **Geospatial:** GeoPandas, SQLAlchemy, Contextily, Shapely.
* **Frontend:** HTML5, Tailwind CSS, Leaflet.js.

---

## 🚀 Installation & Deployment

### Prerequisites
Ensure the following systems are active:
* [Ollama](https://ollama.com/) (running `deepseek-v3` or equivalent, and `llava`).
* PostgreSQL with PostGIS extension enabled.
* Python 3.9+.

### 1. Clone Repository
```bash
git clone [https://github.com/your-username/aegis-geo-agent.git](https://github.com/your-username/aegis-geo-agent.git)
cd aegis-geo-agent