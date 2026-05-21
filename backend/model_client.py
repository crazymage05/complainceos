import os
import google.generativeai as genai
from typing import Optional

PHASE = os.getenv("PROJECT_PHASE", "1")

def get_completion(prompt: str, system: str = "") -> str:
    if PHASE == "1":
        return _gemini_completion(prompt, system)
    else:
        return _ollama_completion(prompt, system)

def _gemini_completion(prompt: str, system: str) -> str:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system if system else None
    )
    response = model.generate_content(prompt)
    return response.text

def _ollama_completion(prompt: str, system: str) -> str:
    import ollama
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = ollama.chat(
        model=os.getenv("OLLAMA_MODEL", "llama3"),
        messages=messages
    )
    return response["message"]["content"]
