import base64

from langchain_core.messages import HumanMessage

from .prompts import VISION_PROMPT


def build_vision_message(image_b64: str, mime_type: str, operator_context: str,
                         prompt: str = VISION_PROMPT) -> HumanMessage:
    text = prompt
    if operator_context and operator_context.strip():
        text += f"\nOPERATOR NOTE: {operator_context.strip()}"
    return HumanMessage(content=[
        {"type": "text", "text": text},
        {"type": "image_url",
         "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
    ])


def analyze_satellite_image(llm, image_data: bytes, operator_context: str = "",
                            mime_type: str = "image/jpeg") -> str:
    img_b64 = base64.b64encode(image_data).decode("utf-8")
    message = build_vision_message(img_b64, mime_type, operator_context)
    return llm.invoke([message]).content
