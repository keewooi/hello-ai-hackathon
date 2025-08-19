import logging
import os

logging.basicConfig(level=logging.INFO)

from google import genai
from google.genai import types
from google.genai.types import HttpOptions

def generate_response(prompt, thinking_budget=0):
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(http_options=HttpOptions(api_version="v1"))

    logging.info(f"Generating response for prompt: {prompt}")
    response = client.models.generate_content(
        model=model,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
        ),
        contents=prompt
    )
    logging.info(f"Generated response: {response}")
    return response