from flask import Flask, Blueprint, render_template, redirect, send_from_directory, request, jsonify, session
from functools import wraps
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from replit.object_storage import Client
import json
import re
import pandas as pd

app = Flask(__name__)
app.secret_key = 'votre_clé_secrète_ici'  # Change this in production

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect('/sultan/login')
        return f(*args, **kwargs)
    return decorated
logger = logging.getLogger(__name__)
client = Client()

class Email:
    def __init__(self, to, subject, content):
        self.to = to if isinstance(to, list) else [to]
        self.subject = subject
        self.content = content

    def send(self):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject
        msg['From'] = "jaffar@hsbc.com"
        msg['To'] = ", ".join(self.to)
        html_part = MIMEText(self.content, 'html')
        msg.attach(html_part)
        try:
            with smtplib.SMTP('localhost') as server:
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

def flatten_dict(dd, separator='_', prefix=''):
    return {
        f"{prefix}{separator}{k}" if prefix else k: v

@app.route('/sultan/login', methods=['GET', 'POST'])
def flatten_dict(dd, separator='_', prefix=''):
    if isinstance(dd, dict):
        return {
            f"{prefix}{separator}{k}" if prefix else k: v
            for kk, vv in dd.items()
            for k, v in flatten_dict(vv, separator, kk).items()
        }
    return {prefix: dd}

def sultan_login():
    if request.method == 'POST':
        if request.form.get('password') == 'sesame':
            session['authenticated'] = True
            return redirect('/sultan')
        return render_template('sultan/login.html', error=True)
    return render_template('sultan/login.html', error=False)

@app.route('/sultan/logout')
def sultan_logout():
    session.pop('authenticated', None)
    return redirect('/sultan/login')

def process_issue_data(issue_data):
    processed_data = {}
    for key, value in issue_data.items():
        if isinstance(value, list):
            processed_data[key] = ', '.join(value)
        elif isinstance(value, dict):
            flattened_dict = flatten_dict(value)
            processed_data.update(flattened_dict)
        else:
            processed_data[key] = value
    return processed_data

def save_in_global_db(key, obj):
    json_object = json.dumps(obj, separators=(',', ':'))
    client.upload_from_text(key, json_object)
    return

def get_one_from_global_db(key):
    content = client.download_from_text(key)
    return json.loads(content)

def get_max_from_global_db(key):
    files = client.list(prefix='jaffar/configs/')
    max_number = -1
    max_object = None
    for file in files:
        remaining_parts = file[len('jaffar/configs/'):]
        match = re.match(r'(\d+)-' + key, remaining_parts)
        if match:
            number = int(match.group(1))
            if number > max_number:
                max_number = number
                max_object = file
    if max_object is not None:
        return get_one_from_global_db(max_object)
    else:
        return "No objects with the given key and a digit at the beginning found."

def get_max_filename_from_global_db(key):
    files = client.list(prefix='jaffar/configs/')
    max_number = -1
    max_object = None
    for file in files:
        remaining_parts = file[len('jaffar/configs/'):]
        match = re.match(r'(\d+)-' + key, remaining_parts)
        if match:
            number = int(match.group(1))
            if number > max_number:
                max_number = number
                max_object = file
    if max_object is not None:
        return max_object
    else:
        return "No objects with the given key and a digit at the beginning found."


def delete(key):
    client.delete(key)
    return

def sendConfirmationEmail(email_address, subject, issue):
    logger.info(f"Sending email to {email_address}")
    issue_data = process_issue_data(issue)
    style = """
    <style>
            table {
                border-collapse: collapse;
                font-family: 'Helvetica';
                font-size:   12px;
            }
            th {
                font-weight: normal
            }
            th, td {
                border: 1px solid #ccc;
                padding: 5px;
                text-align: left;
            }
            td {
                font-family: Helvetica;
                font-size:   12px;
                text-decoration: none;
            }
    </style>
    """
    df = pd.DataFrame(data=issue_data, index=[0])
    df = df.fillna(' ').T
    message = f"""
    <p>Hello,</p>
    <p>Jaffar here!</p>
    <p>I recieved your issue number: {subject}.</p>
    <hr>
    <p><strong>Description of the issue</strong></p>
    <hr>
    <br>
    {df.to_html()}
    <br>
    <br>
    <p>If it requires escalation, you will get another email very soon.</p>
    <br>
    <br>
    <p>All the best,</p>
    """
    content = style + message
    email = Email(
        subject=subject,
        content=content,
    )
    return email.send()


# Routes
@app.route('/login')
def login():
    return render_template('jaffar/login.html')

@app.route('/')
def index():
    return render_template('jaffar/index.html')

@app.route('/sultan')
@requires_auth
def sultan():
    return render_template('sultan/base.html')

@app.route('/questions')
def questions():
    return render_template('sultan/pages/jaffar-questions-studio.html')

@app.route('/questions/import')
def questions_import():
    return render_template('sultan/questions/import.html')

@app.route('/questions/export')
def questions_export():
    return render_template('components/questions/export.html')

@app.route('/questions/url-upload')
def url_upload():
    return render_template('sultan/questions/url_upload.html')

@app.route('/api/upload-config-from-url', methods=['POST'])
def upload_config_from_url():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({"status": "error", "message": "No URL provided"}), 400
            
        # Fetch configuration from URL
        response = requests.get(url)
        response.raise_for_status()
        config_data = response.json()
        
        # Save to object storage
        client.upload_from_text("jaffar/configs/jaffarConfig.json", json.dumps(config_data))
        
        return jsonify({
            "status": "success",
            "message": "Configuration uploaded successfully"
        }), 200
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to fetch configuration: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error processing configuration: {str(e)}"
        }), 500

@app.route('/api/questions', methods=['GET', 'POST'])
def api_questions():
    if request.method == 'GET':
        try:
            latest_config = get_max_from_global_db('jaffarConfig')
            return jsonify(latest_config)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            config_data = request.json
            save_in_global_db('jaffarConfig', config_data)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/upload-config', methods=['POST'])
def upload_config():
    config_data = request.json
    if not config_data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    try:
        json_object = json.dumps(config_data, separators=(',', ':'))
        client.upload_from_text("jaffar/configs/jaffarConfig.json", json_object)
        return jsonify({"status": "success", "message": "Configuration uploaded."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Placeholder for Jaffar and Sultan file serving (adapt as needed)
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)