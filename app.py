from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.prediksi import prediksi_bp
from routes.katalog import katalog_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(prediksi_bp, url_prefix='/api')
app.register_blueprint(katalog_bp, url_prefix='/api')

@app.route('/')
def index():
    return {'message': 'Blueprint Poultry API', 'status': 'running'}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)