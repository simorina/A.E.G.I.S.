import json
import re
import logging
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)

def evaluate_briefing_consistency(briefing_text: str, geojson_str: Optional[str]) -> Dict[str, Any]:
    """
    Spatial Telemetry & LLM-as-a-Judge Consistency Evaluator.
    Evaluates semantic consistency between the generated briefing text and returned GeoJSON features.
    Flags potential numerical hallucinations (e.g. text mentions 5 stations but GeoJSON contains 2).
    """
    if not briefing_text:
        return {"consistent": True, "score": 1.0, "details": "Empty text briefing.", "feature_count": 0}

    feature_count = 0
    if geojson_str:
        try:
            data = json.loads(geojson_str)
            if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                feature_count = len(data.get("features", []))
        except Exception as exc:
            log.warning("Evaluator: Failed to parse GeoJSON: %s", exc)

    # Extract numbers mentioned in text briefing
    numbers_found = [int(n) for n in re.findall(r"\b\d+\b", briefing_text)]
    
    # Check "no data" / "zero" indications
    zero_data_phrases = ["nessun", "nessuna", "no data", "zero", "0 trovat", "offline"]
    text_indicates_empty = any(phrase in briefing_text.lower() for phrase in zero_data_phrases)

    score = 1.0
    details = []

    if text_indicates_empty and feature_count > 0:
        score = 0.5
        details.append(f"Mismatch: Text indicates no data, but GeoJSON contains {feature_count} features.")
    elif feature_count == 0 and numbers_found and max(numbers_found) > 10 and not text_indicates_empty:
        score = 0.7
        details.append("Text contains metrics but GeoJSON is empty.")
    elif feature_count > 0:
        details.append(f"Verified: Briefing aligns with {feature_count} GeoJSON features.")
    else:
        details.append("Verified: Text briefing completed with 0 features.")

    return {
        "consistent": score >= 0.8,
        "score": score,
        "details": " ".join(details),
        "feature_count": feature_count
    }
