from flask import Blueprint, render_template, request, jsonify, redirect, Response
from services.s3_service import list_sultan_objects, get_sultan_object, save_sultan_object, delete_sultan_object
import boto3
from config import BUCKET_NAME, s3

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/pc-analytics-jaffar/dashboards')

@dashboard_bp.route('/')
def index():
    return render_template('/dashboards/index.html')

@dashboard_bp.route('/edit/<dashboard_id>')
def edit(dashboard_id):
    return render_template('sultan/dashboards/edit.html')

@dashboard_bp.route('/new/')
def create_new_dashboard():
    import time
    try:
        timestamp = int(time.time())
        dashboard_id = f'dashboard-{timestamp}'
        
        new_dashboard = {
            'id': dashboard_id,
            'name': 'New Dashboard',
            'description': 'Dashboard created automatically',
            'cards': [],
            'layout': 'grid',
            'order': 0,
            'isPrivate': False,
            'authorizedUsers': [],
            'createdAt': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
        }
        
        if save_sultan_object('dashboards', dashboard_id, new_dashboard):
            return redirect(f'/pc-analytics-jaffar/sultan/dashboard/{dashboard_id}')
        else:
            return "Failed to create dashboard", 500
    except Exception as e:
        return f"Error creating dashboard: {str(e)}", 500

@dashboard_bp.route('/<dashboard_id>')
def view_dashboard(dashboard_id):
    return render_template('/dashboards/index.html')

@dashboard_bp.route('/preview/<dashboard_id>')
def preview_dashboard(dashboard_id):
    return render_template('dashboards/index.html')

# Routes from dashboards_preview.py
@dashboard_bp.route('/dashboards/<dashboard_id>')
def view_dashboard_preview(dashboard_id):
    return render_template('dashboards/index.html')

@dashboard_bp.route('/api/list')
def api_list():
    print(f"DEBUG: api_list route called")
    try:
        dashboards = list_sultan_objects('dashboards')
        print(f"DEBUG: Found {len(dashboards)} dashboards")
        return jsonify(dashboards)
    except Exception as e:
        print(f"DEBUG: Error in api_list: {e}")
        return jsonify([]), 500

@dashboard_bp.route('/api/<dashboard_id>')
def api_get(dashboard_id):
    try:
        dashboard = get_sultan_object('dashboards', dashboard_id)
        return jsonify(dashboard or {})
    except Exception as e:
        return jsonify({}), 404

@dashboard_bp.route('/api/save', methods=['POST'])
def api_save():
    try:
        data = request.json
        dashboard_id = data.get('id')
        if save_sultan_object('dashboards', dashboard_id, data):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to save dashboard"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_bp.route('/api/delete/<dashboard_id>', methods=['DELETE'])
def api_delete(dashboard_id):
    try:
        delete_sultan_object('dashboards', dashboard_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_bp.route('/attachment/')
def view_attachment():
    return render_template('dashboards/attachment.html')

@dashboard_bp.route('/api/file')
def get_file():
    try:
        file_key = request.args.get('key')
        if not file_key:
            return jsonify({"error": "File key is required"}), 400
        
        # Get the file from S3
        response = s3.get_object(Bucket=BUCKET_NAME, Key=file_key)
        file_content = response['Body'].read()
        
        # Determine content type based on file extension
        content_type = 'application/octet-stream'
        if file_key.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif file_key.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif file_key.lower().endswith('.png'):
            content_type = 'image/png'
        elif file_key.lower().endswith('.gif'):
            content_type = 'image/gif'
        elif file_key.lower().endswith('.svg'):
            content_type = 'image/svg+xml'
        elif file_key.lower().endswith('.webp'):
            content_type = 'image/webp'
        
        return Response(
            file_content,
            content_type=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{file_key.split("/")[-1]}"'
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 404