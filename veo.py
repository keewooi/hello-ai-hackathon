import os
import time
from google import genai
from google.cloud import storage
from google.genai.types import Image, GenerateVideosConfig

def generate_video_from_gcs(gcs_uri: str, output_gcs_uri: str) -> str:
    """
    Generates a video from an image in GCS and returns its public URL.

    Args:
        gcs_uri: The GCS URI of the image to use as input.
        output_gcs_uri: The GCS URI where the output video will be saved.

    Returns:
        The public URL of the generated video.
    """
    try:
        # Configure the Gemini client for Vertex AI
        PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
        LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

        # Generate the video
        operation = client.models.generate_videos(
            model="veo-2.0-generate-001",
            prompt="A model twirling around, showcasing the outfit.",
            image=Image(
                gcs_uri=gcs_uri,
                mime_type="image/png",
            ),
            config=GenerateVideosConfig(
                aspect_ratio="9:16", # Portrait aspect ratio for model
                output_gcs_uri=output_gcs_uri,
                generate_audio=False,
            ),
        )
        
        print("Waiting for video generation operation to complete...")

        while not operation.done:
            time.sleep(15)
            operation = client.operations.get(operation)
            print(operation)

        if operation.response:
            # The video is at output_gcs_uri + a generated filename.
            # We need to find the generated video file in the output directory.
            storage_client = storage.Client()
            bucket_name = output_gcs_uri.split('/')[2]
            prefix = '/'.join(output_gcs_uri.split('/')[3:])
            bucket = storage_client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            
            # Find the first video file in the output directory
            for blob in blobs:
                if blob.name.endswith('.mp4'):
                    return blob.public_url
            
            # If no video is found, raise an exception
            raise Exception("Generated video not found in output directory.")
        else:
            raise Exception(f"Video generation failed: {operation.error}")

    except Exception as e:
        print(f"Error generating video: {e}")
        raise