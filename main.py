from flask import Flask, Blueprint, Response, redirect, send_from_directory, request
import logging
import json
import boto3
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

app = Flask(__name__)
logger = logging.getLogger(__name__)


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


# Create blueprint
bp = Blueprint('main', __name__, url_prefix='/')


@bp.route('/')
def serve_entrypoint():
    return redirect("/pc-analytics-jaffar/assets/jaffar/index.html", code=302)


@bp.route('/pc-analytics-jaffar/assets/jaffar/<path:filename>')
def serve_jaffar(filename):
    return send_from_directory('jaffar', filename)


@bp.route('/pc-analytics-jaffar/assets/sultan/<path:filename>')
def serve_sultan(filename):
    return send_from_directory('sultan', filename)


@bp.route('/jaffar/configs/get')
def Get_Config():
    file = request.args.get('file')
    config = get_max_from_global_db(file)
    return config


@bp.route('/jaffar/configs/get-current-name')
def Get_Config_Current_Name():
    file = request.args.get('file')
    config = get_max_filename_from_global_db(file)
    return config


@bp.route('/jaffar/issues/save', methods=['POST'])
def Issue_save():
    data = request.get_json()
    key = f"jaffar/issues/draft/{data['obj']['answers']['_id']}"
    obj = data["obj"]["answers"]
    save_in_global_db(key, obj)
    return {"status": "issue saved"}


@bp.route('/jaffar/issues/submit', methods=['POST'])
def Issue_submit():
    data = request.get_json()
    key = f"jaffar/issues/new/{data['obj']['answers']['_id']}"
    obj = data["obj"]["answers"]
    save_in_global_db(key, obj)
    delete(f"jaffar/issues/draft/{data['obj']['answers']['_id']}")
    sendConfirmationEmail(data['obj']['answers']['author'],
                          data['obj']['answers']['_id'],
                          data['obj']['answers'])
    return {"status": "issue submited"}


# Register blueprint after all routes are defined
app.register_blueprint(bp)
"""
Replit Object Storage configuration
"""
from replit.object_storage import Client

client = Client()


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
    print(json_object)
    client.upload_from_text(key, json_object)
    return


def get_one_from_global_db(key):
    print(f"get from db: {key}")
    content = client.download_from_text(key)
    return json.loads(content)


def get_all_from_global_db():
    files = client.list()
    for file in files:
        print(get_one_from_global_db(file))
    return


def get_max_from_global_db(key):
    files = client.list(prefix='jaffar/configs/')
    max_number = -1
    max_object = None
    for file in files:
        remaining_parts = file[len('jaffar/configs/'):]
        import re
        match = re.match(r'(\d+)-' + key, remaining_parts)
        if match:
            number = int(match.group(1))
            print(
                f"Found number {number} in remaining parts: {remaining_parts}")
            if number > max_number:
                max_number = number
                max_object = file
        else:
            print(f"No number found in remaining parts: {remaining_parts}")
    if max_object is not None:
        print(f"Max number found: {max_number}")
        return get_one_from_global_db(max_object)
    else:
        return "No objects with the given key and a digit at the beginning found."


def get_max_filename_from_global_db(key):
    files = client.list(prefix='jaffar/configs/')
    max_number = -1
    max_object = None
    for file in files:
        remaining_parts = file[len('jaffar/configs/'):]
        import re
        match = re.match(r'(\d+)-' + key, remaining_parts)
        if match:
            number = int(match.group(1))
            print(
                f"Found number {number} in remaining parts: {remaining_parts}")
            if number > max_number:
                max_number = number
                max_object = file
        else:
            print(f"No number found in remaining parts: {remaining_parts}")
    if max_object is not None:
        print(f"Max number found: {max_number}")
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
    print(content)
    email = Email(
        #to=[email_address,"global.control.remediation.programme@noexternalmail.hsbc.com"],
        subject=subject,
        content=content,
    )
    return email.send()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
