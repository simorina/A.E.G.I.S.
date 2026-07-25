from agent.vision import build_vision_message, analyze_satellite_image

def test_message_has_text_and_image_parts():
    msg = build_vision_message("QUJD", "image/png", "")
    parts = msg.content
    assert parts[0]["type"] == "text"
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"] == "data:image/png;base64,QUJD"

def test_operator_context_is_appended():
    msg = build_vision_message("QUJD", "image/jpeg", "look north")
    assert "look north" in msg.content[0]["text"]

def test_no_context_keeps_base_prompt_only():
    msg = build_vision_message("QUJD", "image/jpeg", "   ")
    assert "OPERATOR NOTE" not in msg.content[0]["text"]

def test_analyze_uses_injected_llm():
    class FakeLLM:
        def invoke(self, messages):
            class R: content = "RECON OK"
            return R()
    out = analyze_satellite_image(FakeLLM(), b"ABC", "ctx", "image/jpeg")
    assert out == "RECON OK"
