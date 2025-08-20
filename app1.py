# app.py - Updated Code

import dotenv
import gemini
import json
import os
import time
import uuid
from flask import Flask, render_template, jsonify, request, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from virtual_try_on import generate_virtual_try_on_image
from imagen import rewrite_prompt, generate_image
from google.cloud import storage
import io
from urllib.parse import urlparse
from google.cloud import retail_v2
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = 'super secret key'

dotenv.load_dotenv()

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

GCP_PROJECT_NUMBER = "1003075616886" # Your Project NUMBER
GCP_LOCATION = "global"
CATALOG_ID = "default_catalog"
# ----------------------------------

def convert_to_gs_uri(uri: str) -> str:
    """Converts a public GCS URL to a gs:// URI."""
    if uri.startswith("gs://"):
        return uri
    if uri.startswith("https://storage.googleapis.com/"):
        parsed_url = urlparse(uri)
        return f"gs:/{parsed_url.path}"
    return uri

# --- NEW: API ROUTE FOR VERTEX AI SEARCH ---
@app.route('/api/products')
def get_products():
    """
    Fetches products from the Vertex AI Search for commerce (Retail API) catalog.
    """
    page_token = request.args.get('page_token', None)
    query = request.args.get('q', '')

    try:
        # 1. Initialize two clients: one for searching, one for getting product details.
        search_client = retail_v2.SearchServiceClient()
        product_client = retail_v2.ProductServiceClient() # <-- Client for getting details

        # 2. Define the placement for the search request
        placement = (
            f"projects/{GCP_PROJECT_NUMBER}/locations/{GCP_LOCATION}/"
            f"catalogs/{CATALOG_ID}/servingConfigs/default_search"
        )

        # 3. First call: Perform the search to get product IDs (names)
        search_request = retail_v2.SearchRequest(
            placement=placement,
            query=query,
            visitor_id=str(uuid.uuid4()),
            page_size=9,
            page_token=page_token if page_token else "",
        )
        search_response = search_client.search(request=search_request)

        product_names = [result.product.name for result in search_response.results]

        # Helper function to fetch details for a single product
        def fetch_product_details(name):
            try:
                get_request = retail_v2.GetProductRequest(name=name)
                return product_client.get_product(request=get_request)
            except Exception as e:
                print(f"Could not fetch details for {name}: {e}")
                return None # Return None on error

        # Step 2: Fetch details for all products in parallel for speed
        products = []
        with ThreadPoolExecutor() as executor:
            # The map function runs fetch_product_details for every name in the list concurrently
            full_product_details = executor.map(fetch_product_details, product_names)

            # Process the results as they are completed
            for product_data in full_product_details:
                if product_data:  # Make sure the fetch was successful
                    image_uri = ""
                    if product_data.images:
                        image_uri = product_data.images[0].uri

                    products.append({
                        'id': product_data.id,
                        'title': product_data.title,
                        'image_url': image_uri,
                        'price': product_data.price_info.price if product_data.price_info else None
                    })

        return jsonify({
            'products': products,
            'next_page_token': search_response.next_page_token
        })


    except Exception as e:
        print(f"Error fetching from Vertex AI Retail API: {e}")
        return jsonify({"error": str(e)}), 500
# --------------------------------------------

# --- MODIFIED: The original index route ---
@app.route('/')
def index():
    # We no longer load the JSON file here.
    # The data will be fetched by JavaScript on the frontend.
    return render_template('index.html')
# --------------------------------------------

@app.route('/product/<int:product_id>')
def product(product_id):
    # This route might need to be updated to fetch a SINGLE product
    # from Vertex AI search if you still use a product detail page.
    # For now, we leave it as is.
    with open('products.json') as f:
        products = json.load(f)
    product = next((p for p in products if p['id'] == product_id), None)
    if product:
        return render_template('product.html', product=product)
    return "Product not found", 404

# (The rest of your app.py code remains the same...)

@app.route('/api/generate-image', methods=['POST'])
def generate_image_route():
    data = request.get_json()
    description = data.get('description')
    if not description:
        return jsonify({'error': 'Description is required'}), 400

    # Generate a unique filename
    import time
    filename = f"generated_{int(time.time())}.png"
    path = f"static/images/{filename}"

    try:
        # Generate the image
        gemini.generate_image(description, path)
        # Return the path to the image
        return jsonify({'image_url': f'/{path}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/imagen-inspire', methods=['POST'])
def imagen_route():
    data = request.get_json()
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    try:
        # Rewrite the prompt
        rewritten_prompt = rewrite_prompt(prompt)
        
        # Generate the image
        generated_image = generate_image(rewritten_prompt)
        
        # Generate a unique filename for the output image
        output_filename = f"imagen_{int(time.time())}.png"
        
        # Upload to GCS
        storage_client = storage.Client()
        bucket_name = GCS_BUCKET_NAME
        if bucket_name.startswith("gs://"):
            bucket_name = bucket_name[5:]
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"inspire/{output_filename}")
        
        # Convert PIL image to bytes
        img_byte_arr = io.BytesIO()
        pil_image = generated_image._pil_image if hasattr(generated_image, '_pil_image') else generated_image
        pil_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        blob.upload_from_string(img_byte_arr, content_type='image/png')

        return jsonify({'image_url': blob.public_url, 'rewritten_prompt': rewritten_prompt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/virtual-try-on', methods=['POST'])
def virtual_try_on_route():
    data = request.get_json()
    person_image_gcs_uri = data.get('person_image_gcs_uri')
    apparel_gcs_uris = data.get('apparel_gcs_uris')

    if not person_image_gcs_uri:
        return jsonify({'error': 'person_image_gcs_uri is required'}), 400
    
    if not apparel_gcs_uris:
        return jsonify({'error': 'apparel_gcs_uris is required'}), 400

    person_image_path = convert_to_gs_uri(person_image_gcs_uri)
    clothing_image_paths = [convert_to_gs_uri(uri) for uri in apparel_gcs_uris]

    try:
        generated_image = generate_virtual_try_on_image(person_image_path, clothing_image_paths)
        
        # Generate a unique filename for the output image
        output_filename = f"vto_{int(time.time())}.png"
        
        # Upload to GCS
        storage_client = storage.Client()
        bucket_name = GCS_BUCKET_NAME
        if bucket_name.startswith("gs://"):
            bucket_name = bucket_name[5:]
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"vto/{output_filename}")
        
        # Convert PIL image to bytes
        img_byte_arr = io.BytesIO()
        pil_image = generated_image._pil_image  # Get the underlying PIL image
        pil_image.save(img_byte_arr, format='PNG')  # Call save on the PIL image
        img_byte_arr = img_byte_arr.getvalue()
        
        blob.upload_from_string(img_byte_arr, content_type='image/png')

        return jsonify({'image_url': blob.public_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_to_virtual_try_on')
def add_to_virtual_try_on():
    image_url = request.args.get('image_url')
    images = session.get('product_images', [])
    if image_url not in images:
        images.append(image_url)
        session['product_images'] = images
    return redirect(url_for('virtual'))

@app.route('/virtual')
def virtual():
    images = session.get('product_images', [])
    return render_template('virtual.html', images=images)

@app.route('/remove_from_virtual_try_on')
def remove_from_virtual_try_on():
    image_url = request.args.get('image_url')
    images = session.get('product_images', [])
    if image_url in images:
        images.remove(image_url)
        session['product_images'] = images
    return redirect(url_for('virtual'))
@app.route('/generated_product')
def generated_product():
    image_url = request.args.get('image_url')
    description = request.args.get('description')
    product = {
        'name': 'Generated Product',
        'image_urls': {
            'large': image_url
        },
        'description': {
            'long': description
        },
        'rating': 'N/A',
        'reviews': []
    }
    return render_template('generated_product.html', product=product)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        
        # Upload to GCS
        storage_client = storage.Client()
        bucket_name = GCS_BUCKET_NAME
        if bucket_name.startswith("gs://"):
            bucket_name = bucket_name[5:]
        bucket = storage_client.bucket(bucket_name)
        
        # Add a timestamp to the filename to avoid overwriting files
        blob = bucket.blob(f"uploads/{int(time.time())}_{filename}")
        
        blob.upload_from_file(file, content_type=file.content_type)
        
        return jsonify({'image_url': blob.public_url})


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    app.run(debug=True)