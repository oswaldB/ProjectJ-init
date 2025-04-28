
from flask import Blueprint, request, jsonify, render_template, redirect
from services.storage import save_in_global_db, get_one_from_global_db, delete
import logging

logger = logging.getLogger(__name__)
sultan = Blueprint('sultan', __name__)

@sultan.route('/login')
def login():
    return render_template('sultan/login.html')

@sultan.route('/')
def index():
    return render_template('sultan/base.html')

@sultan.route('/forms')
def forms_list():
    return render_template('sultan/forms/index.html')

@sultan.route('/forms/edit/<form_id>')
def form_edit(form_id):
    return render_template('sultan/forms/edit.html')

@sultan.route('/api/sultan/forms/list')
def api_forms_list():
    forms = []
    prefix = 'sultan/forms/'
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in response.get('Contents', []):
            try:
                response = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                content = response['Body'].read().decode('utf-8')
                form = json.loads(content)
                forms.append(form)
            except Exception as e:
                logger.error(f"Failed to load form {obj['Key']}: {e}")
    except Exception as e:
        logger.error(f"Failed to list forms: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify(forms)
