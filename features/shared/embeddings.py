import os
from typing import Optional
from features.shared.observability import BackendObservability, audit_token_budget

def get_embedding(text: str, conversation_id: Optional[str] = None) -> list[float] | None:
    """Generates a 768-dimension vector embedding for the given text using gemini-embedding-2.
    
    Returns None if GEMINI_API_KEY is not set or is 'mock-key', or if an error occurs.
    """
    import sys
    is_testing = "unittest" in sys.modules or "pytest" in sys.modules

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "mock-key":
        err_msg = "GEMINI_API_KEY is not set or is 'mock-key'. Real services are required."
        BackendObservability.warning(
            err_msg,
            conversation_id=conversation_id
        )
        if is_testing:
            raise RuntimeError(err_msg)
        return None
        
    try:
        # Audit token budget using estimated tokens (roughly 1 token per 4 characters)
        prompt_tokens = (len(text or "") + 3) // 4
        audit_token_budget(
            conversation_id=conversation_id or "unknown",
            prompt_tokens=prompt_tokens,
            candidate_tokens=0
        )
        
        from google import genai
        from google.genai import types
        
        client = genai.Client()
        response = client.models.embed_content(
            model="gemini-embedding-2",
            contents=text or " ",
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        if response and response.embeddings:
            return response.embeddings[0].values
    except Exception as e:
        BackendObservability.error(
            f"Embedding generation failed: {e}.",
            exception=e,
            conversation_id=conversation_id
        )
        if is_testing:
            raise RuntimeError(f"Embedding generation failed in test: {e}") from e
        
    return None

