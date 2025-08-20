import dotenv
import gemini
import json

from flask import Flask, render_template, jsonify, request, send_file

app = Flask(__name__)

dotenv.load_dotenv()

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

if __name__ == '__main__':
    app.run(debug=True)