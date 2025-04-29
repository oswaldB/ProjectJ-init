from flask import Flask, Blueprint, render_template, redirect, request, jsonify
import json
import logging
import boto3
from moto import mock_aws
import os
import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
logger = logging.getLogger(__name__)
email_executor = ThreadPoolExecutor(max_workers=2)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Local storage configuration
LOCAL_BUCKET_DIR = "./local_bucket"
BUCKET_NAME = "jaffar-bucket"
os.makedirs(LOCAL_BUCKET_DIR, exist_ok=True)

# Initialize mocked AWS
def restore_local_to_s3():
    for root, _, files in os.walk(LOCAL_BUCKET_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            s3_key = os.path.relpath(local_path, LOCAL_BUCKET_DIR)
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
                try:
                    s3.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=content)
                except Exception as e:
                    logger.error(f"Failed to restore {s3_key} to S3: {e}")

mock = mock_aws()
mock.start()

# Create S3 client and bucket
s3 = boto3.client('s3', region_name='us-east-1')
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
except:
    pass

restore_local_to_s3()

class CircularRefEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except:
            return str(obj)

def save_in_global_db(key, obj):
    json_object = json.dumps(obj, separators=(',', ':'), cls=CircularRefEncoder)
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json_object)
        full_path = os.path.join(LOCAL_BUCKET_DIR, key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding='utf-8') as f:
            f.write(json_object)
        return True
    except Exception as e:
        logger.error(f"Failed to save data: {e}")
        return False

def get_one_from_global_db(key):
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except:
        try:
            local_path = os.path.join(LOCAL_BUCKET_DIR, key)
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.loads(f.read())
        except Exception as e:
            logger.error(f"Failed to get data: {e}")
            raise

def delete(key):
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)
    full_path = os.path.join(LOCAL_BUCKET_DIR, key)
    if os.path.exists(full_path):
        os.remove(full_path)

@app.route('/login')
def login():
    if request.path == '/login':
        return render_template('login.html')
    return redirect('/')

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.path == '/login':
            return f(*args, **kwargs)
        if not request.headers.get('user_email'):
            current_path = request.path
            return redirect(f'/login?redirect={current_path}')
        return f(*args, **kwargs)
    return decorated

from routes.jaffar_routes import jaffar_bp
from routes.sultan_routes import sultan_bp

app.register_blueprint(jaffar_bp)
app.register_blueprint(sultan_bp, url_prefix='/sultan')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)