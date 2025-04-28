from flask import Flask
from routes.jaffar import jaffar
from routes.sultan import sultan
import os

app = Flask(__name__)

# Create local storage directory
LOCAL_BUCKET_DIR = "./local_bucket"
os.makedirs(LOCAL_BUCKET_DIR, exist_ok=True)

# Register blueprints
app.register_blueprint(jaffar, url_prefix='/')
app.register_blueprint(sultan, url_prefix='/sultan')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)