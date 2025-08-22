# GenAI E-Commerce Fashion Platform

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.0-blue.svg)
![Google Cloud](https://img.shields.io/badge/google--cloud-platform-blue.svg)

## Overview

This project is a proof-of-concept for a generative AI-powered e-commerce fashion platform. It demonstrates how to integrate several of Google Cloud's cutting-edge AI technologies to create a unique and interactive shopping experience. Users can search for products, visualize how clothing items would look on a person, and even generate entirely new clothing designs based on their own creative ideas.

## Core Components

The application is built around three core generative AI features:

*   **Vertex AI Search (VAIS):** The platform leverages VAIS for a powerful and intelligent product search experience. Instead of relying on simple keyword matching, it uses Google's advanced search technology to understand user intent and deliver more relevant results from the product catalog.

*   **Virtual Try-On:** This feature allows users to select a person's image and one or more clothing items to see a realistic rendering of how the apparel would look on that person. It uses a specialized generative model to combine the images, providing a powerful visualization tool for shoppers.

*   **Imagen-Powered Design Generation ("Inspire Me"):** For users seeking something truly unique, the "Inspire Me" feature uses Imagen, Google's text-to-image model, to generate novel clothing designs from a text prompt. The application first uses a powerful language model to refine the user's prompt for optimal results, then feeds it to Imagen to create a high-quality image of the new product.

## Architecture and Flow

The application is a web-based platform built with a Flask backend and a standard HTML, CSS, and JavaScript frontend. It integrates with Google Cloud services for its core AI functionalities.

1.  **Frontend:** The user interacts with the web interface to browse products, use the Virtual Try-On feature, or generate new designs.
2.  **Backend (Flask):** The Flask server handles user requests, communicates with the Google Cloud APIs, and serves the appropriate data and pages.
3.  **Google Cloud Services:**
    *   **Vertex AI Search:** Powers the product search functionality.
    *   **Gemini & Imagen Models:** Used for the Virtual Try-On and design generation features.
    *   **Google Cloud Storage (GCS):** Stores product images, user uploads, and generated images.

## Key Files

*   **`app.py`**: The main Flask application file. It contains all the routes and logic for handling web requests, integrating with the AI services, and managing user sessions.
*   **`virtual_try_on.py`**: This module contains the logic for interacting with the Virtual Try-On API. It takes a person's image and clothing images as input and returns the generated try-on image.
*   **`imagen.py`**: This module handles the image generation functionality. It includes functions for rewriting user prompts for better results and for calling the Imagen API to generate the final image.
*   **`notebooks/feature-vais.py`**: This notebook provides a detailed example of how to use the Vertex AI Search API to query the product catalog.
*   **`templates/`**: This directory contains all the HTML templates for the web pages, including the home page, product pages, and the Virtual Try-On interface.
*   **`static/`**: This directory holds all the static assets, such as CSS, JavaScript, and images.

## Setup and Installation

### Prerequisites

*   A Google Cloud project with the Vertex AI API enabled.
*   A Google Cloud Storage bucket.
*   Python 3.9+
*   [uv](https://docs.astral.sh/uv/) (for package management)

### Project Setup

1.  **Clone the Repository:**
    ```bash
    git clone <YOUR_REPO_URL>
    cd hello-ai-hackathon
    ```
2.  **Configure Environment Variables:**
    Make a copy of `env.example` and save it as `.env`. Update the values in the `.env` file with your Google Cloud project details:
    ```
    GCS_BUCKET_NAME="gs://your-gcs-bucket-name"
    VAIS_GCP_PROJECT_NUMBER="your-gcp-project-number"
    VAIS_GCP_LOCATION="global"
    VAIS_CATALOG_ID="default_catalog"
    ```
3.  **Install Dependencies:**
    ```bash
    uv sync
    ```

## Running the Application

To start the Flask development server, run the following command:

```bash
uv run app.py
```

The application will be available at `http://127.0.0.1:5000`.

## Production Deployment (to Cloud Run)

```bash
export project="ksaw-demo"
export app="uniglow"

gcloud builds submit --tag gcr.io/$project/$app

# remember to update the values below
gcloud run deploy $app --image gcr.io/$project/$app --platform managed --allow-unauthenticated --region asia-southeast1 --max-instances=1 --min-instances=0 --memory 1G --no-cpu-throttling --timeout 3600 \
--set-env-vars "GOOGLE_CLOUD_PROJECT=$project" \
--set-env-vars "GOOGLE_CLOUD_LOCATION=us-central1" \
--set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=True" \
--set-env-vars "GCS_BUCKET_NAME=helloai-genmedia" \
--set-env-vars "VAIS_GCP_PROJECT_NUMBER=1003075616886" \
--set-env-vars "VAIS_GCP_LOCATION=global" \
--set-env-vars "VAIS_CATALOG_ID=default_catalog"
```
