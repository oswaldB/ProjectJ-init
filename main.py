import logging
from flask import Flask

app = Flask(__name__)

logger = logging.getLogger(__name__)


# custom health check
def custom_health_check():
    return Response(status=200, response="Custom health check OK")


app = Blueprint(__name__, health_check_func=custom_health_check)

@app.route('/')
def serve_entrypoint():
    return redirect("/pc-analytics-jaffar/assets/jaffar/index.html", code=302)


@app.route('/pc-analytics-jaffar/assets/jaffar/<path:filename>')
def serve_jaffar(filename):
    # Using request args for path will expose you to directory traversal attacks
    return send_from_directory('jaffar', filename)


@app.route('/pc-analytics-jaffar/assets/sultan/<path:filename>')
def serve_sultan(filename):
    # Using request args for path will expose you to directory traversal attacks
    return send_from_directory('sultan', filename)


@app.route('/jaffar/configs/get')
def Get_Config():
    file = request.args.get('file')
    config = get_max_from_global_db(file)
    return config

@app.route('/jaffar/configs/get-current-name')
def Get_Config_Current_Name():
    file = request.args.get('file')
    config = get_max_filename_from_global_db(file)
    return config


@app.route('/jaffar/issues/save', methods=['POST'])
def Issue_save():
    data = request.get_json()
    key = f"jaffar/issues/draft/{data['obj']['answers']['_id']}"
    obj = data["obj"]["answers"]
    save_in_global_db(key, obj)
    return {"status": "issue saved"}


@app.route('/jaffar/issues/submit', methods=['POST'])
def Issue_submit():
    data = request.get_json()
    key = f"jaffar/issues/new/{data['obj']['answers']['_id']}"
    obj = data["obj"]["answers"]
    save_in_global_db(key, obj)
    delete(f"jaffar/issues/draft/{data['obj']['answers']['_id']}")
    sendConfirmationEmail(data['obj']['answers']['author'],data['obj']['answers']['_id'],data['obj']['answers'])
    return {"status": "issue submited"}



"""
SG configuration
"""


endpoint = settings.SG_URL
access_key = settings.SG_ID_KEY
secret_key = settings.SG_SECRET
bucket_name = settings.SG_BUCKET

storage_obj_config = {
    "aws_access_key_id": access_key,
    "aws_secret_access_key": secret_key,
    "endpoint_url": endpoint
}
client = boto3.client("s3", **storage_obj_config)
bucket = bucket_name

"""
Helpers
"""


## Write in DB
def save_in_global_db(key, obj):
    json_object = json.dumps(obj,separators=(',', ':'))
    print(json_object)
    client.put_object(
        Body=f"{json_object}",
        Bucket=bucket,
        Key=key,
    )
    return


## Read from DB
def get_one_from_global_db(key):
    print(f"get from db: {key}")
    response = client.get_object(
        Bucket=bucket,
        Key=key
    )
    json_content = json.loads(response['Body'].read())
    return json_content


## LIst from db
def get_all_from_global_db():
    folder = client.list_objects(
        Bucket=bucket
    )

    for object in folder['Contents']:
        print(get_one_from_global_db(object['Key']))

    return

## get the latest config file
def get_max_from_global_db(key):
    folder = client.list_objects(
        Bucket=bucket,
        Prefix='jaffar/configs/'  # Add prefix to only search for objects within the jaffar/configs/ folder
    )

    max_number = -1
    max_object = None
    for obj in folder['Contents']:
        # Check if the object key starts with the input key after the 'jaffar/configs/' prefix
        remaining_parts = obj['Key'][len('jaffar/configs/'):]

        # Use regex to find the first number in the remaining characters
        import re
        match = re.match(r'(\d+)-' + key, remaining_parts)  # Match number-name format

        # If a number is found, compare it to the current maximum number
        if match:
            number = int(match.group(1))
            print(f"Found number {number} in remaining parts: {remaining_parts}")
            if number > max_number:
                max_number = number
                max_object = obj
        else:
            print(f"No number found in remaining parts: {remaining_parts}")

    if max_object is not None:
        print(f"Max number found: {max_number}")
        return get_one_from_global_db(max_object['Key'])
    else:
        return "No objects with the given key and a digit at the beginning found."

def get_max_filename_from_global_db(key):
    folder = client.list_objects(
    Bucket=bucket,
    Prefix='jaffar/configs/' # Add prefix to only search for objects within the jaffar/configs/ folder
    )

    max_number = -1
    max_object = None
    for obj in folder['Contents']:
        # Check if the object key starts with the input key after the 'jaffar/configs/' prefix
        remaining_parts = obj['Key'][len('jaffar/configs/'):]

        # Use regex to find the first number in the remaining characters
        import re
        match = re.match(r'(\d+)-' + key, remaining_parts)  # Match number-name format

        # If a number is found, compare it to the current maximum number
        if match:
            number = int(match.group(1))
            print(f"Found number {number} in remaining parts: {remaining_parts}")
            if number > max_number:
                max_number = number
                max_object = obj
        else:
            print(f"No number found in remaining parts: {remaining_parts}")

    if max_object is not None:
        print(f"Max number found: {max_number}")
        return max_object['Key']
    else:
        return "No objects with the given key and a digit at the beginning found."

def delete(key):
    client.delete_object(
        Bucket=bucket,
        Key=key
    )
    return

def sendConfirmationEmail(email_address: str, subject:str, issue:dict) -> bool:
        """
        Send the confirmation email to the author email address.
        """
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
        <p>If it requires escalation, you will get another email very soon.</p.
        <br>
        <br>
        <p>All the best,</p>
        """

        content = style + message

        print(content)

        # create an email
        email = Email(
            to=[email_address,"global.control.remediation.programme@noexternalmail.hsbc.com"],
            subject=subject,
            content=content,
        )
        email.send()
        return True

def flatten_dict(dd: Dict, separator='_', prefix=''):
    """
    Flattens a nested dictionary and concatenates the keys with a separator.
    """
    return {f"{prefix}{separator}{k}" if prefix else k: v
            for kk, vv in dd.items()
            for k, v in flatten_dict(vv, separator, kk).items()
            } if isinstance(dd, dict) else {prefix: dd}

def process_issue_data(issue_data):
    """
    Converts list-type values to strings and flattens nested dictionaries.
    """
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

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000)

