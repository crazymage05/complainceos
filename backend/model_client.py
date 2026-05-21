import os
from google import genai
from google.genai import types

PHASE = os.getenv("PROJECT_PHASE", "1")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


def get_completion(prompt: str, system: str = "") -> str:
    if PHASE == "1":
        return _gemini_completion(prompt, system)
    return _ollama_completion(prompt, system)


def get_embedding(text: str) -> list[float]:
    """Return 768-dim embedding vector using text-embedding-004."""
    client = _get_client()
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
    )
    return list(response.embeddings[0].values)


def _gemini_completion(prompt: str, system: str) -> str:
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system if system else None
    ) if system else None
    response = client.models.generate_content(
        model="gemini-2.0-flash",
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
