
from flask import Blueprint, render_template, request, jsonify
import json
import os
from services.db_service import save_in_global_db, load_from_global_db

workflow_bp = Blueprint('workflow', __name__, url_prefix='/sultan/workflows')

@workflow_bp.route('/')
def index():
    return render_template('sultan/workflows/index.html')

@workflow_bp.route('/edit/<workflow_id>')
def edit(workflow_id):
    return render_template('sultan/workflows/edit.html')

@workflow_bp.route('/api/list')
def api_list():
    try:
        workflows = []
        bucket_path = 'local_bucket/sultan/workflows/'
        if os.path.exists(bucket_path):
            for filename in os.listdir(bucket_path):
                if filename.endswith('.json'):
                    with open(os.path.join(bucket_path, filename), 'r') as f:
                        workflow = json.load(f)
                        workflows.append(workflow)
        return jsonify(workflows)
    except Exception as e:
        return jsonify([]), 500

@workflow_bp.route('/api/<workflow_id>')
def api_get(workflow_id):
    try:
        workflow = load_from_global_db(f'sultan/workflows/{workflow_id}.json')
        return jsonify(workflow)
    except:
        return jsonify({}), 404

@workflow_bp.route('/api/save', methods=['POST'])
def api_save():
    try:
        data = request.json
        workflow_id = data.get('id')
        save_in_global_db(f'sultan/workflows/{workflow_id}.json', data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@workflow_bp.route('/api/delete/<workflow_id>', methods=['DELETE'])
def api_delete(workflow_id):
    try:
        file_path = f'local_bucket/sultan/workflows/{workflow_id}.json'
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
