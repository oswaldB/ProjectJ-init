from flask import Blueprint, render_template, jsonify, request, redirect  # Add import for redirect
import logging
import json  # Add import for JSON
import datetime  # Add import for datetime
from werkzeug.utils import secure_filename
from services.email_service import Email
from services.s3_service import (
    save_in_global_db,
    delete,
    get_max_from_global_db,
    get_one_file,
    list_folder_with_filter,
    upload_file_to_s3
)
import boto3
import os
from config import BUCKET_NAME, s3

logger = logging.getLogger(__name__)

# Create a blueprint for forms
forms_blueprint = Blueprint('forms', __name__, url_prefix='/pc-analytics-jaffar/forms')

@forms_blueprint.route('/')
def forms_index():
    return render_template('forms/form.html')

@forms_blueprint.route('/edit/<form_id>')
@forms_blueprint.route('/edit/<form_id>/')
def forms_edit(form_id):
    return render_template('forms/form.html', form_id=form_id)

@forms_blueprint.route('/edit/<form_id>/response-<response_id>')
def redirect_to_form_edit(form_id, response_id):
    """
    Redirects to the form edit page based on the form_id.
    """
    return redirect(f"/pc-analytics-jaffar/forms/edit/{form_id}/")

@forms_blueprint.route('/api/list', methods=['GET'])
def api_forms_list():
    """
    Fetch the list of forms from S3.
    """
    forms = []
    prefix = 'sultan/forms/'
    try:
        logger.info(f"Listing forms with prefix: {prefix}")
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        logger.info(f"S3 response: {response}")
        
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.json'):
                try:
                    form_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                    form_data = json.loads(form_obj['Body'].read().decode('utf-8'))
                    forms.append(form_data)
                    logger.info(f"Loaded form: {form_data.get('id', 'unknown')}")
                except Exception as e:
                    logger.error(f"Failed to load form {key}: {e}")
        
        logger.info(f"Total forms found: {len(forms)}")
        return jsonify(forms)
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/save', methods=['POST'])
def api_forms_save():
    """
    Save a form to S3 in JSON format.
    """
    data = request.json
    form = data.get('form')
    if not form:
        return jsonify({"error": "Invalid form data"}), 400
    key = f'forms/{form["id"]}.json'
    try:
        json_data = form # Removed ensure_ascii
        save_in_global_db(key, json_data)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save form: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/delete/<form_id>', methods=['DELETE'])
def api_forms_delete(form_id):
    """
    Delete a form from S3.
    """
    key = f'forms/{form_id}.json'
    try:
        delete(key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete form: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/config/<form_id>', methods=['GET'])
def api_form_config(form_id):
    """
    Fetch the form configuration from S3 based on the form_id.
    """
    key = f'sultan/forms/{form_id}.json'
    try:
        config = get_one_file(key)
        if not config:
            return jsonify({"error": "Form configuration not found"}), 404
        return jsonify(config)
    except Exception as e:
        logger.error(f"Failed to fetch form configuration for {form_id}: {e}")
        return jsonify({"error": "Failed to fetch form configuration"}), 500

@forms_blueprint.route('/api/auto-save/<form_id>', methods=['POST'])
def api_auto_save(form_id):
    """
    Auto-save all answers to a single file in S3 with a timestamp-based ID and author in JSON format.
    """
    data = request.json
    response_id = data.get('responseId')
    answers = data.get('answers')
    author = data.get('author', 'Anonymous')  # Default to 'Anonymous' if no author is provided
    if not response_id or not answers:
        return jsonify({"error": "Invalid data provided"}), 400
    key = f'forms/{form_id}/{response_id}.json'
    try:
        json_data = {"responseId": response_id, "answers": answers, "author": author}  # Removed ensure_ascii
        save_in_global_db(key, json_data)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to auto-save answers for form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/submit/<form_id>', methods=['POST'])
def api_submit_form(form_id):
    """
    Submit the response file by moving it to the forms/formid/ directory in S3 in JSON format.
    """
    response_id = request.json.get('responseId')
    if not response_id:
        return jsonify({"error": "Response ID is missing"}), 400
    source_key = f'forms/{form_id}/{response_id}.json'
    destination_key = f'forms/{form_id}/submitted/{response_id}.json'
    config_key = f'sultan/forms/{form_id}.json'
    try:
        # Retrieve the response file
        response_data = get_one_file(source_key)
        if not response_data:
            return jsonify({"error": "Response file not found"}), 404
        # Save the file to the new location in JSON format
        json_data = response_data  # Removed ensure_ascii
        save_in_global_db(destination_key, json_data)
        # Delete the original file
        delete(source_key)
        # Retrieve the form configuration
        form_config = get_one_file(config_key)
        print(form_config.keys()) 
        if not form_config:
            return jsonify({"error": "Form configuration not found"}), 404
        # Handle email configuration if enabled
        if not isinstance(form_config, dict):
            logger.error(f"form_config is not a dict: {form_config}")
            return jsonify({"error": "Invalid form configuration format"}), 500
        # Access emailConf directly from form_config
        logger.info(f"Form config keys: {list(form_config.keys())}")
        fields = form_config.get("fields", [])
        # Chercher emailConf dans les champs
        email_conf = None
        for field in fields:
            if "emailConf" in field:
                email_conf = field["emailConf"]
                break
        if not email_conf:
            # emailConf peut aussi être à la racine du form_config
            email_conf = form_config.get("emailConf")
        logger.info(f"Email config: {email_conf}")
        if isinstance(email_conf, str):
            try:
                email_conf = json.loads(email_conf)
            except Exception as parse_error:
                logger.error(f"Failed to parse email_conf string: {parse_error}")
                email_conf = None
        if email_conf and email_conf.get("enabled") is True:
            json_data = response_data if isinstance(response_data, dict) else json.loads(response_data)
            author_email = json_data.get("author", "").split(" - ")[-1]
            if author_email:
                answers = json_data.get("answers", {})
                answers = {k: v for k, v in answers.items() if v not in (None, "", [], {})}
                logger.info(f"Answers for email: {answers}")
                # Define the email style and format the answers into an HTML table
                style = """
                <style>
                    table {
                        border-collapse: collapse;
                        font-family: 'Helvetica';
                        font-size: 12px;
                    }
                    th {
                        font-weight: normal;
                    }
                    th, td {
                        border: 1px solid #ccc;
                        padding: 5px;
                        text-align: left;
                    }
                    td {
                        font-family: Helvetica;
                        font-size: 12px;
                        text-decoration: none;
                    }
                </style>
                """
                answers_table = "<table><tr><th>Question</th><th>Answer</th></tr>"
                for key, value in answers.items():
                    answers_table += f"<tr><td>{key}</td><td>{value}</td></tr>"
                answers_table += "</table>"
                email_body = f"""
                <p>Hello,</p>
                <p>Thank you for filling out your form.</p>
                <hr>
                <p><strong>Here is a summary of your responses:</strong></p>
                <hr>
                <br>
                {answers_table}
                <br>
                <p>All the best,</p>
                """
                content = style + email_body
                logger.info(f"Sending email to {author_email} with body:\n{content}")
                email = Email(
                    subject=email_conf.get("subject", "Form Submission Success"),
                    content=content,
                    to=[author_email],
                    cc=email_conf.get("cc", "").split(",") if email_conf.get("cc") else []
                )
                logger.info(f"Email object created: {email}")
                try:
                    email.send()
                except Exception as email_error:
                    logger.error(f"Failed to send email to {author_email}: {email_error}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to submit form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/upload', methods=['POST'])
def api_upload_file():
    """
    Upload a file to S3 and return the file path.
    """
    form_id = request.form.get('formId')
    answer_id = request.form.get('answerId')  # New parameter for answer ID
    file = request.files.get('file')
    if not form_id or not answer_id or not file:
        return jsonify({"error": "Form ID, Answer ID, or file is missing"}), 400
    try:
        filename = secure_filename(file.filename)
        file.filename = filename  # Ensure the filename is sanitized
        s3_key = f'forms/{form_id}/{answer_id}/attachments/{filename}'  # Construct the S3 key
        upload_file_to_s3(file, s3_key)  # Use the generic function
        return jsonify({"status": "success", "fileKey": s3_key})  # Return the S3 file path
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/delete-file', methods=['DELETE'])
def api_delete_file():
    """
    Delete a file from S3.
    """
    data = request.json
    file_key = data.get('fileKey')
    if not file_key:
        return jsonify({"error": "File key is missing"}), 400
    try:
        delete(file_key)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete file {file_key}: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/create-response', methods=['POST'])
def api_create_response():
    """
    Create a new response for a form and return the response ID.
    """
    data = request.json
    form_id = data.get('formId')

    if not form_id:
        return jsonify({"error": "Form ID is missing"}), 400

    try:
        response_id = f'response-{int(datetime.datetime.now().timestamp() * 1000)}'
        response_data = {
            "id": response_id,
            "formId": form_id,
            "status": "new",
            "createdAt": datetime.datetime.now().isoformat(),
            "updatedAt": datetime.datetime.now().isoformat(),
            "answers": {}
        }
        key = f'forms/{form_id}/{response_id}.json'
        save_in_global_db(key, response_data)
        return jsonify({"status": "success", "responseId": response_id})
    except Exception as e:
        logger.error(f"Failed to create response for form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/submitted-responses/<form_id>', methods=['GET'])
def api_submitted_responses(form_id):
    """
    Fetch submitted responses for a form from S3 with pagination.
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        prefix = f'forms/{form_id}/submitted/'
        all_keys = []

        # List all submitted responses
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('/'):
                continue
            all_keys.append((key, obj.get('LastModified')))

        # Sort by last modified date (descending)
        all_keys.sort(key=lambda x: x[1] or '', reverse=True)
        total = len(all_keys)
        start = (page - 1) * page_size
        end = start + page_size
        page_keys = all_keys[start:end]

        # Fetch only the current page's responses
        responses = []
        for key, _ in page_keys:
            try:
                response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                response_data = json.loads(response_obj['Body'].read().decode('utf-8'))
                responses.append(response_data.get('answers', {}))
            except Exception as e:
                logger.error(f"Error loading response {key}: {e}")

        return jsonify({
            "issues": responses,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        logger.error(f"Error in api_submitted_responses: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/pouchdb/init/<form_id>', methods=['POST'])
def api_pouchdb_init(form_id):
    """
    Initialize PouchDB with data from S3 for the given form ID.
    """
    logger.info(f"Initializing PouchDB for form {form_id}")
    prefix = f'forms/{form_id}/submitted/'
    try:
        # List all submitted responses
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        chunks = []
        
        if 'Contents' not in response:
            logger.info(f"No submitted data found for form {form_id}")
            return jsonify({"chunks": []}), 200
            
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('/'):
                continue
            response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            response_data = json.loads(response_obj['Body'].read().decode('utf-8'))
            chunks.append(response_data.get('answers', {}))

        logger.info(f"Found {len(chunks)} submitted responses for form {form_id}")
        
        # Split data into chunks for PouchDB
        chunk_size = 100
        chunked_data = [chunks[i:i + chunk_size] for i in range(0, len(chunks), chunk_size)]
        return jsonify({"chunks": chunked_data}), 200
    except Exception as e:
        logger.error(f"Failed to initialize PouchDB for form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/pouchdb/init-drafts/<form_id>', methods=['POST'])
def api_pouchdb_init_drafts(form_id):
    """
    Initialize PouchDB with draft data from S3 for the given form ID.
    """
    logger.info(f"Initializing PouchDB with drafts for form {form_id}")
    prefix = f'forms/{form_id}/'
    try:
        # List all draft responses (excluding submitted folder)
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        chunks = []
        
        if 'Contents' not in response:
            logger.info(f"No draft data found for form {form_id}")
            return jsonify({"chunks": []}), 200
            
        for obj in response.get('Contents', []):
            key = obj['Key']
            # Skip files in the submitted folder
            if '/submitted/' in key or key.endswith('/'):
                continue
            # Only process JSON files that are direct children of the form folder
            if key.count('/') != 2 or not key.endswith('.json'):
                continue
                
            response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            response_data = json.loads(response_obj['Body'].read().decode('utf-8'))
            chunks.append(response_data.get('answers', {}))

        logger.info(f"Found {len(chunks)} draft responses for form {form_id}")
        
        # Split data into chunks for PouchDB
        chunk_size = 100
        chunked_data = [chunks[i:i + chunk_size] for i in range(0, len(chunks), chunk_size)]
        return jsonify({"chunks": chunked_data}), 200
    except Exception as e:
        logger.error(f"Failed to initialize PouchDB with drafts for form {form_id}: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/get-draft/<form_id>', methods=['GET'])
def api_get_draft(form_id):
    """
    Fetch draft responses for a form from S3, excluding submitted folder.
    Returns documents in /forms/form-id/ but not in /forms/form-id/submitted/
    """
    try:
        prefix = f'forms/{form_id}/'
        all_documents = []

        # List all objects in the form folder
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            # Skip files in the submitted folder
            if '/submitted/' in key or key.endswith('/'):
                continue
            # Only process JSON files that are direct children of the form folder
            if key.count('/') != 2 or not key.endswith('.json'):
                continue
            
            try:
                response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                response_data = json.loads(response_obj['Body'].read().decode('utf-8'))
                all_documents.append(response_data)
            except Exception as e:
                logger.error(f"Error loading draft document {key}: {e}")

        logger.info(f"Found {len(all_documents)} draft documents for form {form_id}")
        return jsonify(all_documents)
    except Exception as e:
        logger.error(f"Error in api_get_draft: {e}")
        return jsonify({"error": str(e)}), 500

@forms_blueprint.route('/api/draft-responses/<form_id>', methods=['GET'])
def api_draft_responses(form_id):
    """
    Fetch draft responses for a form from S3 with pagination.
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        prefix = f'forms/{form_id}/'
        all_keys = []

        # List all draft responses (excluding submitted folder)
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            # Skip files in the submitted folder
            if '/submitted/' in key or key.endswith('/'):
                continue
            # Only process JSON files that are direct children of the form folder
            if key.count('/') != 2 or not key.endswith('.json'):
                continue
            all_keys.append((key, obj.get('LastModified')))

        # Sort by last modified date (descending)
        all_keys.sort(key=lambda x: x[1] or '', reverse=True)
        total = len(all_keys)
        start = (page - 1) * page_size
        end = start + page_size
        page_keys = all_keys[start:end]

        # Fetch only the current page's responses
        responses = []
        for key, _ in page_keys:
            try:
                response_obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                response_data = json.loads(response_obj['Body'].read().decode('utf-8'))
                responses.append(response_data.get('answers', {}))
            except Exception as e:
                logger.error(f"Error loading draft response {key}: {e}")

        return jsonify({
            "issues": responses,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        logger.error(f"Error in api_draft_responses: {e}")
        return jsonify({"error": str(e)}), 500