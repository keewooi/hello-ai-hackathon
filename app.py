import dotenv
import gemini
import json
import os
import time
import uuid
from flask import Flask, render_template, jsonify, request, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from virtual_try_on import generate_virtual_try_on_image
from veo import generate_video_from_gcs
from imagen import rewrite_prompt, generate_image
from google.cloud import storage
import io
from urllib.parse import urlparse
from google.cloud import retail_v2
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)
app.secret_key = 'super secret key'

dotenv.load_dotenv()

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
VAIS_GCP_PROJECT_NUMBER = os.environ.get("VAIS_GCP_PROJECT_NUMBER")
VAIS_GCP_LOCATION = os.environ.get("VAIS_GCP_LOCATION")
VAIS_CATALOG_ID = os.environ.get("VAIS_CATALOG_ID")

# In-memory store for video generation status
video_status = {}

def convert_to_gs_uri(uri: str) -> str:
    """Converts a public GCS URL to a gs:// URI."""
    if uri.startswith("gs://"):
        return uri
    if uri.startswith("https://storage.googleapis.com/"):
        parsed_url = urlparse(uri)
        # The path will be /<bucket-name>/<object-path>
        # We need to remove the leading '/'
        return f"gs:/{parsed_url.path}"
    return uri

@app.route('/')
def index():
    with open('products.json') as f:
        products = json.load(f)
    
    # Pass a few featured products to the home page
    return render_template('index.html', products=products[:3])

@app.route('/products')
def products():
    with open('products.json') as f:
        curated_products = json.load(f)
    return render_template('products.html', curated_products=curated_products)

@app.route('/product/<path:product_id>')
def product(product_id):
    # If the product_id is a full resource name, use it directly.
    # Otherwise, assume it's a numeric ID from the JSON file.
    if 'projects/' in product_id:
        try:
            product_client = retail_v2.ProductServiceClient()
            get_request = retail_v2.GetProductRequest(name=product_id)
            product_data = product_client.get_product(request=get_request)

            image_uri = ""
            if product_data.images:
                image_uri = product_data.images[0].uri

            product_details = {
                'id': product_data.id,
                'name': product_data.title,
                'image_urls': { 'large': image_uri, 'small': image_uri, 'medium': image_uri, 'small_set':[image_uri] },
                'price': product_data.price_info.price if product_data.price_info else None,
                'description': { 'long': product_data.description }
            }

            print(product_details)
            
            return render_template('product.html', product=product_details)
        except Exception as e:
            print(f"Could not fetch product {product_id} from Vertex AI Search: {e}")
            return "Product not found", 404
    else:
        # Fallback to JSON for numeric IDs
        try:
            numeric_id = int(product_id)
            with open('products.json') as f:
                products = json.load(f)
            product = next((p for p in products if p['id'] == numeric_id), None)

            print(product)
            if product:
                return render_template('product.html', product=product)
        except (ValueError, StopIteration):
            pass  # Not a numeric ID or not found in JSON

    return "Product not found", 404

@app.route('/api/products')
def get_products():
    """
    Fetches products from the Vertex AI Search for commerce (Retail API) catalog.
    """
    page_token = request.args.get('page_token', None)
    query = request.args.get('q', '')
    try:
        page_size = int(request.args.get('page_size', 9))
    except (TypeError, ValueError):
        page_size = 9


    try:
        # 1. Initialize two clients: one for searching, one for getting product details.
        search_client = retail_v2.SearchServiceClient()
        product_client = retail_v2.ProductServiceClient() # <-- Client for getting details

        # 2. Define the placement for the search request
        placement = (
            f"projects/{VAIS_GCP_PROJECT_NUMBER}/locations/{VAIS_GCP_LOCATION}/"
            f"catalogs/{VAIS_CATALOG_ID}/servingConfigs/default_search"
        )

        # 3. First call: Perform the search to get product IDs (names)
        search_request = retail_v2.SearchRequest(
            placement=placement,
            query=query,
            visitor_id=str(uuid.uuid4()),
            page_size=page_size,
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
                        'id': product_data.name,
                        'name': product_data.title,
                        'image_urls': { 'small': image_uri, 'large': image_uri },
                        'price': product_data.price_info.price if product_data.price_info else None
                    })

        return jsonify({
            'products': products,
            'next_page_token': search_response.next_page_token
        })


    except Exception as e:
        print(f"Error fetching from Vertex AI Retail API: {e}")
        return jsonify({"error": str(e)}), 500

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
        rewritten_prompt, title = rewrite_prompt(prompt)
        
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

        return jsonify({'image_url': blob.public_url, 'rewritten_prompt': rewritten_prompt, 'title': title})
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
        if not person_image_path.startswith("gs://"):
            # It's a local file path, so we need to upload it to GCS
            storage_client = storage.Client()
            bucket_name = GCS_BUCKET_NAME
            if bucket_name.startswith("gs://"):
                bucket_name = bucket_name[5:]
            bucket = storage_client.bucket(bucket_name)
            
            filename = f"profile_photos/{int(time.time())}_{os.path.basename(person_image_path)}"
            blob = bucket.blob(filename)
            blob.upload_from_filename(person_image_path)
            person_image_path = f"gs://{bucket.name}/{blob.name}"

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
        pil_image = generated_image._pil_image
        pil_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        blob.upload_from_string(img_byte_arr, content_type='image/png')

        # Use the public URL as the generation ID
        generation_id = blob.public_url
        video_status[generation_id] = {'status': 'processing', 'url': None}

        # Start video generation in a background thread
        video_thread = threading.Thread(target=generate_and_store_video, args=(generation_id, blob.name))
        video_thread.start()

        session['vto_image_url'] = blob.public_url
        session['vto_person_image'] = person_image_path
        session['vto_clothing_images'] = clothing_image_paths
        return jsonify({'image_url': blob.public_url, 'generation_id': generation_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_and_store_video(generation_id, image_blob_name):
    try:
        image_gcs_uri = f"gs://{GCS_BUCKET_NAME}/{image_blob_name}"
        video_filename = f"veo_{int(time.time())}.mp4"
        output_video_gcs_uri = f"gs://{GCS_BUCKET_NAME}/veo/{video_filename}"
        
        video_url = generate_video_from_gcs(image_gcs_uri, output_video_gcs_uri)
        video_status[generation_id] = {'status': 'done', 'url': video_url}
    except Exception as e:
        print(f"Video generation failed for {generation_id}: {e}")
        video_status[generation_id] = {'status': 'failed', 'url': None}

@app.route('/api/poll-video/<path:generation_id>')
def poll_video(generation_id):
    status = video_status.get(generation_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/api/save-video-url', methods=['POST'])
def save_video_url():
    data = request.get_json()
    video_url = data.get('video_url')
    if video_url:
        session['vto_video_url'] = video_url
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'message': 'No URL provided'}), 400

@app.route('/add_to_virtual_try_on')
def add_to_virtual_try_on():
    image_url = request.args.get('image_url')
    title = request.args.get('title', 'Generated Product')
    images = session.get('product_images', [])
    
    # Check if the image_url is already in the list
    found = False
    for item in images:
        if isinstance(item, dict) and item['image_url'] == image_url:
            found = True
            break
        elif isinstance(item, str) and item == image_url:
            found = True
            break
            
    if not found:
        images.append({'image_url': image_url, 'title': title})
        session['product_images'] = images
        
    return redirect(url_for('virtual'))

@app.route('/virtual')
def virtual():
    images = session.get('product_images', [])
    vto_image_url = session.get('vto_image_url')
    vto_person_image = session.get('vto_person_image')
    vto_clothing_images = session.get('vto_clothing_images')
    vto_video_url = session.get('vto_video_url')

    # Get uploaded models from GCS
    storage_client = storage.Client()
    bucket_name = GCS_BUCKET_NAME
    if bucket_name.startswith("gs://"):
        bucket_name = bucket_name[5:]
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix="profile_photos/")
    uploaded_models = [blob.public_url for blob in blobs]


    # Check if the selected images have changed
    current_clothing_images = []
    for item in images:
        if isinstance(item, dict):
            current_clothing_images.append(item['image_url'])
        else:
            current_clothing_images.append(item)

    current_clothing_gs_uris = [convert_to_gs_uri(uri) for uri in current_clothing_images]
    if vto_image_url and vto_clothing_images and set(vto_clothing_images) == set(current_clothing_gs_uris):
        return render_template('virtual.html', images=images, vto_image_url=vto_image_url, vto_video_url=vto_video_url, uploaded_models=uploaded_models)
    else:
        # Clear the old VTO image if the items have changed
        session.pop('vto_image_url', None)
        session.pop('vto_video_url', None)
        session.pop('vto_person_image', None)
        session.pop('vto_clothing_images', None)
        return render_template('virtual.html', images=images, uploaded_models=uploaded_models)

@app.route('/remove_from_virtual_try_on')
def remove_from_virtual_try_on():
    image_url_to_remove = request.args.get('image_url')
    images = session.get('product_images', [])
    images = [item for item in images if (isinstance(item, dict) and item['image_url'] != image_url_to_remove) or (isinstance(item, str) and item != image_url_to_remove)]
    session['product_images'] = images
    return redirect(url_for('virtual'))
@app.route('/generated_product')
def generated_product():
    image_url = request.args.get('image_url')
    description = request.args.get('description')
    title = request.args.get('title')
    product = {
        'name': title,
        'image_urls': {
            'large': image_url
        },
        'description': {
            'long': description
        },
        'rating': 'N/A',
        'reviews': []
    }
    return render_template('generated_product.html', product=product, title=title)

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    total_price = sum(item.get('price', 0) for item in cart_items)
    return render_template('cart.html', cart=cart_items, total_price=total_price)

@app.route('/add_to_cart')
def add_to_cart():
    product_images = session.get('product_images', [])
    cart = session.get('cart', [])
    
    with open('products.json') as f:
        all_products = json.load(f)

    for item in product_images:
        # Avoid adding duplicates
        if any(cart_item.get('image_url') == (item.get('image_url') if isinstance(item, dict) else item) for cart_item in cart):
            continue

        if isinstance(item, dict):
            # For generated items, add with a default price
            cart.append({
                'image_url': item.get('image_url'),
                'title': item.get('title', 'Generated Product'),
                'price': item.get('price', 49.99)  # Default price for generated items
            })
        else:
            # For existing products, find details from products.json
            product = next((p for p in all_products if p['image_urls']['large'] == item), None)
            if product:
                cart.append({
                    'id': product.get('id'),
                    'image_url': item,
                    'title': product.get('name'),
                    'price': product.get('price')
                })

    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/remove_from_cart')
def remove_from_cart():
    image_url = request.args.get('image_url')
    cart = session.get('cart', [])
    cart = [item for item in cart if item.get('image_url') != image_url]
    session['cart'] = cart
    return redirect(url_for('cart'))


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
        blob = bucket.blob(f"profile_photos/{int(time.time())}_{filename}")
        
        blob.upload_from_file(file, content_type=file.content_type)

        return jsonify({'gcs_uri': f'gs://{bucket.name}/{blob.name}'})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    app.run(debug=True)