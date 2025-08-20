import dotenv
import gemini
import json
import os
import time
from flask import Flask, render_template, jsonify, request, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from virtual_try_on import generate_virtual_try_on_image
from imagen import rewrite_prompt, generate_image
from google.cloud import storage
import io
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'super secret key'

dotenv.load_dotenv()

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

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
        all_products = json.load(f)
    return render_template('products.html', products=all_products)

@app.route('/product/<int:product_id>')
def product(product_id):
    with open('products.json') as f:
        products = json.load(f)
    product = next((p for p in products if p['id'] == product_id), None)
    if product:
        return render_template('product.html', product=product)
    return "Product not found", 404

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
    return render_template('virtual.html', images=images)

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