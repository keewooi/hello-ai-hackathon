import dotenv
import gemini

from flask import Flask, render_template, jsonify, request, send_file

app = Flask(__name__)

dotenv.load_dotenv()

@app.route('/')
def index():
    my_variable = "SohAI"
    # response = gemini.generate_response("What is the meaning of life?")
    return render_template('index.html', my_variable=my_variable)

if __name__ == '__main__':
    app.run(debug=True)