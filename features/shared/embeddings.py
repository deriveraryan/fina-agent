import os
import logging

def get_embedding(text: str) -> list[float]:
    """Generates a 768-dimension vector embedding for the given text using gemini-embedding-2.
    
    Raises ValueError if GEMINI_API_KEY is not set or is 'mock-key'.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "mock-key":
        raise ValueError("GEMINI_API_KEY is not set or is 'mock-key'. Real services are required.")
        
    try:
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
        # Fallback to zero vector on network error to prevent fatal crashes
        logging.warning(f"Embedding generation failed: {e}. Falling back to zero vector.")
        
    return [0.0] * 768
