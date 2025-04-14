from flask import Flask, Blueprint, render_template, redirect, send_from_directory, request, jsonify
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
#import replit.object_storage #Removed
import json
import re
import pandas as pd
import boto3

app = Flask(__name__)
logger = logging.getLogger(__name__)
#client = Client() #Removed

# Replace with your S3 bucket name
bucket_name = "your-s3-bucket-name" #Add this line.  Replace your-s3-bucket-name with your actual bucket name.
s3 = boto3.client('s3')


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
        for kk, vv in dd.items()
        for k, v in flatten_dict(vv, separator, kk).items()
    } if isinstance(dd, dict) else {
        prefix: dd
    }


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
    s3.put_object(Bucket=bucket_name, Key=key, Body=json_object)
    return


def get_one_from_global_db(key):
    response = s3.get_object(Bucket=bucket_name, Key=key)
    content = response['Body'].read().decode('utf-8')
    return json.loads(content)


def get_max_from_global_db(key):
    files = []
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='jaffar/configs/')
        for obj in response.get('Contents', []):
            files.append(obj['Key'])

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
    except Exception as e:
        logger.error(f"Error in get_max_from_global_db: {e}")
        return None


def get_max_filename_from_global_db(key):
    files = []
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='jaffar/configs/')
        for obj in response.get('Contents', []):
            files.append(obj['Key'])

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
    except Exception as e:
        logger.error(f"Error in get_max_filename_from_global_db: {e}")
        return None



def delete(key):
    s3.delete_object(Bucket=bucket_name, Key=key)
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
        to=email_address, #Added email_address here
        subject=subject,
        content=content,
    )
    return email.send()


# Routes
@app.route('/login')
def login():
    if request.path == '/login':
        return render_template('login.html')
    return redirect('/')


def require_auth(f):
    from functools import wraps
    from flask import request, redirect, url_for

    @wraps(f)
    def decorated(*args, **kwargs):
        if request.path == '/login':
            return f(*args, **kwargs)

        if not request.headers.get('user_email') and not request.cookies.get(
                'user_email'):
            current_path = request.path
            return redirect(f'/login?redirect={current_path}')
        return f(*args, **kwargs)

    return decorated


@app.route('/')
def index():
    return render_template('jaffar/index.html')


@app.route('/sultan/login')
def sultan_login():
    return render_template('sultan/login.html')


@app.route('/sultan')
def sultan():
    return render_template('sultan/base.html')


@app.route('/sultan/<path:path>')
def sultan_pages(path):
    return render_template(f'sultan/{path}')


@app.route('/questions')
def questions():
    return render_template('sultan/pages/jaffar-questions-studio.html')


@app.route('/questions/import')
def questions_import():
    return render_template('sultan/questions/import.html')


@app.route('/questions/export')
def questions_export():
    return render_template('components/questions/export.html')


@app.route('/sultan/forms/list')
def forms_list():
    return render_template('sultan/forms/list.html')


@app.route('/sultan/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')


@app.route('/api/sultan/forms/list')
def api_forms_list():
    forms = []
    draft_prefix = 'sultan/configs/draft/forms/'

    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=draft_prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=bucket_name, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                form = json.loads(content)

                # Add status if not present
                if 'status' not in form:
                    form['status'] = 'Draft'

                # Add last_modified if not present
                metadata = s3.head_object(Bucket=bucket_name, Key=obj['Key'])
                if 'last_modified' not in form:
                    form['last_modified'] = metadata['LastModified']

                forms.append(form)
            except Exception as e:
                logger.error(f"Failed to load form {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify(forms)


@app.route('/api/sultan/forms/<form_id>')
def api_form_get(form_id):
    try:
        content = s3.get_object(Bucket=bucket_name, Key=f'sultan/configs/draft//forms/{form_id}.json')['Body'].read().decode('utf-8')
        return jsonify(json.loads(content))
    except Exception as e:
        logger.error(f"Failed to load form {form_id}: {e}")
        return jsonify({"error": "Form not found"}), 404


@app.route('/api/sultan/forms/save', methods=['POST'])
def api_form_save():
    data = request.json
    form = data.get('form')

    if not form:
        return jsonify({"error": "Form required"}), 400

    try:
        # Ensure directory structure exists
        form_path = f'sultan/configs/draft/forms/{form["id"]}.json'

        # Save form as JSON
        json_data = json.dumps(form, indent=2, ensure_ascii=False)
        s3.put_object(Bucket=bucket_name, Key=form_path, Body=json_data)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": "Failed to save form"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)