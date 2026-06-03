import os
import time
from google import genai
from google.genai import types

PHASE = os.getenv("PROJECT_PHASE", "1")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


def _is_transient(err: str) -> bool:
    """429 (rate limit) and 503/UNAVAILABLE (model overloaded) are transient —
    a short backoff usually clears them."""
    e = err.lower()
    return ("429" in e or "503" in e or "unavailable" in e
            or "overloaded" in e or "high demand" in e)


def get_completion(prompt: str, system: str = "") -> str:
    for attempt in range(3):
        try:
            if PHASE == "1":
                return _gemini_completion(prompt, system)
            return _ollama_completion(prompt, system)
        except Exception as e:
            # Retry transient 429/503 with backoff; 503 clears fast so use a
            # shorter wait than the rate-limit case.
            if _is_transient(str(e)) and attempt < 2:
                is_overload = "503" in str(e) or "unavailable" in str(e).lower()
                time.sleep((2 if is_overload else 5) * (attempt + 1))
                continue
            raise


def get_embedding(text: str) -> list[float]:
    """Return 3072-dim embedding vector using gemini-embedding-001."""
    client = _get_client()
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text,
    )
    return list(response.embeddings[0].values)


def _gemini_completion(prompt: str, system: str) -> str:
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system if system else None
    ) if system else None
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )
    return response.text


def _ollama_completion(prompt: str, system: str) -> str:
    import ollama
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = ollama.chat(
        model=os.getenv("OLLAMA_MODEL", "llama3"),
        messages=messages,
    )
    return response["message"]["content"]


def get_vision_completion(prompt: str, file_bytes: bytes, mime_type: str) -> str:
    """
    Multimodal Gemini call: pass a PDF or image alongside a text prompt.
    Returns the extracted/analysed text.

    Used by the circular OCR endpoint — a small-business owner can upload
    a scanned PDF of a government notification and ComplianceOS reads it.
    """
    client = _get_client()
    file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
    text_part = types.Part.from_text(text=prompt)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[file_part, text_part],
    )
    return response.text or ""
