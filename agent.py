import os
import re
import base64
from sqlalchemy import create_engine
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.sql_database.query import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage

# --- 1. CONFIGURAZIONE ---
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "192.168.1.48")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
TARGET_SCHEMA = os.getenv("TARGET_SCHEMA", "schema1")
LLM_URL = os.getenv("LLM_URL", "192.168.1.48:11434")

DB_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- 2. SETUP DATABASE E LLM ---
engine = None
db = None
llm = None
llm = None

try:
    # Creazione Engine SQLAlchemy
    engine = create_engine(DB_URI)
    # Creazione Wrapper LangChain
    db = SQLDatabase.from_uri(DB_URI, schema=TARGET_SCHEMA)
    
    print(f"TABELLE RILEVATE: {db.get_table_names()}")
    print("--- Connessione DB Riuscita (Backend) ---")
except Exception as e:
    print(f"--- ERRORE Connessione DB: {e} ---")

# Inizializzazione LLM (Text/SQL)
llm = ChatOllama(model="qwen3-vl:235b-cloud", temperature=0, base_url=LLM_URL)



# --- 3. FUNZIONI DI UTILITÀ ---
def extract_sql_from_response(llm_response: str) -> str:
    """
    Pulisce l'output dell'LLM per estrarre solo la query SQL valida.
    """
    clean_text = llm_response.replace("```sql", "").replace("```", "").strip()
    match = re.search(r'\b(WITH|SELECT)\b', clean_text, re.IGNORECASE)
    
    if match:
        clean_text = clean_text[match.start():]
    
    if ";" in clean_text:
        clean_text = clean_text.split(";")[0]
        
    return clean_text

def analyze_satellite_image(image_data: bytes) -> str:
    """
    Prende i byte di un'immagine, li converte in base64 e interroga il Vision Model.
    """
    # 1. Encode Base64
    img_b64 = base64.b64encode(image_data).decode("utf-8")
    
    # 2. Prompt Tattico
    prompt_text = """
    ROLE: Tactical Geospatial Analyst.
    TASK: Analyze this satellite image of the Milan area.
    OUTPUT: Provide a brief, military-style report covering:
    1. Urban Density (High/Medium/Low).
    2. Key Infrastructure (Roads, Rails, Water bodies).
    3. Potential Obstacles or Cover.
    
    Keep it concise and actionable.
    """

    # 3. Costruzione Messaggio Multimodale LangChain
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
            },
        ]
    )
    
    # 4. Invocazione
    response = llm.invoke([message])
    return response.content
# --- 4. TEMPLATES & PROMPTS (SQL) ---
sql_template = """
### ROLE
You are a Senior PostGIS Data Engineer specialized in geospatial queries for the city of Milan.
Your goal is to generate accurate, efficient, and syntactically correct PostgreSQL/PostGIS queries based on natural language requests.

### DATABASE SCHEMA
{table_info}

### GUIDELINES & CONSTRAINTS

1. **Schema Awareness**:
   - ALWAYS prefix table names with the schema name (e.g., `schema_name.table_name`).
   - NEVER hallucinate columns. Use ONLY the columns defined in the provided tables.
2. **Query Structure**:
    - Always in output the geometry column must be included if present in the table (can assume different names like: geom, geometry, the_geom).
### ERROR CORRECTION
If a previous error occurred, analyze it deeply.
PREVIOUS ERROR: {error}
INSTRUCTION: If the error is not empty, you must rewrite the query to fix the specific logic or syntax issue described above.

### INPUT
USER REQUEST: {input}
DEFAULT LIMIT: {top_k}

### SQL
"""

sql_prompt = ChatPromptTemplate.from_template(sql_template)

# --- 5. CHAIN DEFINITIONS ---
if db and llm:  
    generate_query_chain = create_sql_query_chain(llm, db, sql_prompt, k=100)
else:
    generate_query_chain = None

# Chain per il sommario testuale
summary_template = """
Analyze the following data:
{data_summary}

You are a virtual assistant.
Write a short and helpful response for the user based on the data above.
Response:
"""
summary_prompt = ChatPromptTemplate.from_template(summary_template)
summary_chain = summary_prompt | llm | StrOutputParser()