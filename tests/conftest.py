import os
import sys

# Garantisce che la root del progetto sia importabile (package `agent`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
