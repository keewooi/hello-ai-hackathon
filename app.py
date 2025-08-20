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
    return render_template('index.html', products=products)

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
    person_image_path = None
    if 'person_image_gcs_uri' in request.form:
        person_image_path = convert_to_gs_uri(request.form['person_image_gcs_uri'])
    elif 'person_image' in request.files:
        person_image_file = request.files['person_image']
        if person_image_file.filename != '':
            person_image_filename = secure_filename(person_image_file.filename)
            person_image_path = os.path.join(app.config['UPLOAD_FOLDER'], person_image_filename)
            person_image_file.save(person_image_path)

    if not person_image_path:
        return jsonify({'error': 'Person image (as file or GCS URI) is required'}), 400

    clothing_image_paths = []
    if 'clothing_images' in request.files:
        clothing_files = request.files.getlist('clothing_images')
        for file in clothing_files:
            if file.filename != '':
                filename = secure_filename(file.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                clothing_image_paths.append(path)

    if 'apparel_gcs_uris' in request.form:
        gcs_uris = request.form.getlist('apparel_gcs_uris')
        clothing_image_paths.extend([convert_to_gs_uri(uri) for uri in gcs_uris])

    if not clothing_image_paths:
        return jsonify({'error': 'At least one clothing image (as file or GCS URI) is required'}), 400

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

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    app.run(debug=True)