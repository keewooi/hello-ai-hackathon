import os
import typing
from PIL import Image as PIL_Image
from google import genai
from google.genai import types

# Configure the Gemini client
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

def rewrite_prompt(prompt: str) -> tuple[str, str]:
    """
    Rewrites a given prompt using the Gemini API for better image generation.

    Args:
        prompt: The user's initial prompt.

    Returns:
        The rewritten prompt.
    """
    rewrite_model = "gemini-2.5-pro"
    response = client.models.generate_content(
        model=rewrite_model,
        contents=[f"You are a fashion expert and also an expert in LLM Prompting for Google's Image Generation Model, Imagen. "
                  f"The user wants to describe their ideal piece of clothing. "
                  f"First, create a short, catchy title (5 words or less) for the clothing item. "
                  f"Then, rewrite the following prompt into a single, enhanced prompt for a text-to-image model. "
                  f"Focus on creating a visually rich and detailed description of a **single** piece of clothing. Do not provide multiple options or explanations. "
                  f"The image must be in the style of professional studio photography. "
                  f"The image must not include a model, just the **single** piece of clothing. "
                  f"If no gender is specified, default to a gender neutral style. "
                  f"Output the title and the rewritten prompt on separate lines, with the title first. "
                  f"Original prompt: '{prompt}'"]
    )
    # The model sometimes still returns the prompt in quotes, so we remove them.
    parts = response.text.strip().split('\n')
    title = parts[0]
    rewritten = '\n'.join(parts[1:])
    if rewritten.startswith('"') and rewritten.endswith('"'):
        rewritten = rewritten[1:-1]
    return rewritten, title

def generate_image(prompt: str) -> PIL_Image.Image:
    """
    Generates an image using the Imagen API from a given prompt.

    Args:
        prompt: The prompt to generate the image from.

    Returns:
        The generated image as a PIL Image object.
    """
    generation_model = "imagen-4.0-fast-generate-001"
    
    response = client.models.generate_images(
        model=generation_model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
            image_size="2K",
            safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
            person_generation="ALLOW_ADULT",
        ),
    )
    
    return response.generated_images[0].image