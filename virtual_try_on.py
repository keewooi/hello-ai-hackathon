import os
import typing
from PIL import Image as PIL_Image
from google import genai
from google.genai.types import Image, ProductImage, RecontextImageSource, RecontextImageConfig

# Configure the Gemini client
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

def generate_virtual_try_on_image(person_image_path: str, clothing_image_paths: list[str]) -> PIL_Image.Image:
    """
    Generates a virtual try-on image using the Gemini API.

    Args:
        person_image_path: The local path or GCS URI of the person's image.
        clothing_image_paths: A list of local paths or GCS URIs for the clothing items.

    Returns:
        The generated image as a PIL Image object.
    """
    virtual_try_on_model = "virtual-try-on-preview-08-04"

    # Load the person image
    if person_image_path.startswith("gs://"):
        person_image = Image(gcs_uri=person_image_path)
    else:
        person_image = Image.from_file(location=person_image_path)

    # Load the clothing images
    product_images = []
    for path in clothing_image_paths:
        if path.startswith("gs://"):
            product_images.append(ProductImage(product_image=Image(gcs_uri=path)))
        else:
            product_images.append(ProductImage(product_image=Image.from_file(location=path)))

    # Generate the initial image with the first clothing item
    response = client.models.recontext_image(
        model=virtual_try_on_model,
        source=RecontextImageSource(
            person_image=person_image,
            product_images=[product_images[0]],
        ),
        config=RecontextImageConfig(
            base_steps=32,
            number_of_images=1,
            safety_filter_level="BLOCK_LOW_AND_ABOVE",
            person_generation="ALLOW_ADULT",
        ),
    )
    generated_image = response.generated_images[0].image

    # If there are more clothing items, apply them sequentially
    # This also means that if the same type of clothing is applied (i.e. multiple tops), the last top will be the output.
    for i in range(1, len(product_images)):
        response = client.models.recontext_image(
            model=virtual_try_on_model,
            source=RecontextImageSource(
                person_image=generated_image,
                product_images=[product_images[i]],
            ),
            config=RecontextImageConfig(
                base_steps=32,
                number_of_images=1,
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="ALLOW_ADULT",
            ),
        )
        generated_image = response.generated_images[0].image

    return generated_image