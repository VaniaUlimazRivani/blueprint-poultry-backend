from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.prediksi import prediksi_bp
from routes.katalog import katalog_bp
from routes.pengelola import pengelola_bp
from routes.model_performa import model_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(prediksi_bp, url_prefix='/api')
app.register_blueprint(katalog_bp, url_prefix='/api')
app.register_blueprint(pengelola_bp, url_prefix='/api')
app.register_blueprint(model_bp, url_prefix='/api')

@app.route('/')
def index():
    return {'message': 'Blueprint Poultry API', 'status': 'running'}

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)