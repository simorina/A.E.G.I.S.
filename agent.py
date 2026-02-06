import os
import re
import base64
from typing import Optional
from sqlalchemy import create_engine
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.sql_database.query import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv()  # Load environment variables from .env file

class Config:
    DB_URI = f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@" \
             f"{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    SCHEMA = os.environ["TARGET_SCHEMA"]
    LLM_URL = os.environ["LLM_URL"]
    MODEL_NAME = os.environ["MODEL_NAME"]


# --- 2. COMPONENTS INITIALIZATION ---
try:
    print("Connecting to DB...")
    print(f"DB URI: {Config.DB_URI}")
    print(f"Schema: {Config.SCHEMA}")
    print("LLM URL:", Config.LLM_URL)
    print("Model Name:", Config.MODEL_NAME)
    print("Initializing database connection...")
    engine = create_engine(Config.DB_URI)
    db = SQLDatabase.from_uri(Config.DB_URI, schema=Config.SCHEMA)
    print(f"Connected to DB. Tables: {db.get_table_names()}")
except Exception as e:
    print(f"Critical DB Error: {e}")
    db = None
    engine = None

# LLM Initialization
llm = ChatOllama(model=Config.MODEL_NAME, temperature=0, base_url=Config.LLM_URL)

# --- 3. CORE FUNCTIONS ---
def extract_sql_from_response(llm_response: str) -> str:
    """Cleans LLM output to extract executable SQL."""
    clean_text = re.sub(r'```sql|```', '', llm_response, flags=re.IGNORECASE).strip()
    match = re.search(r'\b(WITH|SELECT)\b', clean_text, re.IGNORECASE)
    if match:
        clean_text = clean_text[match.start():]
    
    
    return clean_text.split(';')[0] if ';' in clean_text else clean_text

def analyze_satellite_image(image_data: bytes) -> str:
    """Processes image bytes via Vision Model."""
    img_b64 = base64.b64encode(image_data).decode("utf-8")
    
    # PROMPT INVARIATO (Come richiesto)
    prompt_text = """
    ROLE: Tactical Geospatial Analyst.
    TASK: Analyze this satellite image of the Milan area.
    OUTPUT: Provide a brief, military-style report covering:
    1. Urban Density (High/Medium/Low).
    2. Key Infrastructure (Roads, Rails, Water bodies).
    3. Potential Obstacles or Cover.
    
    Keep it concise and actionable.
    """

    message = HumanMessage(content=[
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
    ])
    
    return llm.invoke([message]).content

# --- 4. PROMPTS & CHAINS ---
# SQL_TEMPLATE INVARIATO (Come richiesto)
sql_template = """
### ROLE
You are a Senior PostGIS Data Engineer specialized in geospatial queries for the city of Milan.
Your goal is to generate accurate, efficient, and syntactically correct PostgreSQL/PostGIS queries based on natural language requests.

### DATABASE SCHEMA
{table_info}

### GUIDELINES & CONSTRAINTS

1. **Schema Awareness**:
   - ALWAYS prefix table names with the schema name (e.g., `schema_name.table_name`), in your case use schema1
   - NEVER hallucinate columns. Use ONLY the columns defined in the provided tables.
2. **Query Structure**:
    - the table called parks, already have a geom column, so use that.
    - the other tables don't have a geom column so, if you have to use them, use postgis functions to create geometries from longitude and latitude columns.
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
generate_query_chain = create_sql_query_chain(llm, db, sql_prompt, k=100) if db else None

# SUMMARY_TEMPLATE INVARIATO (Come richiesto)
summary_template = """
Analyze the following data:
{data_summary}

You are a virtual assistant.
Write a short and helpful response for the user based on the data above.
Response:
"""
summary_chain = ChatPromptTemplate.from_template(summary_template) | llm | StrOutputParser()