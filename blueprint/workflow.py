
from flask import Blueprint, render_template, request, jsonify
from services.db_service import list_sultan_objects, get_sultan_object, save_sultan_object, delete_sultan_object

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
        workflows = list_sultan_objects('workflows')
        return jsonify(workflows)
    except Exception as e:
        return jsonify([]), 500

@workflow_bp.route('/api/<workflow_id>')
def api_get(workflow_id):
    try:
        workflow = get_sultan_object('workflows', workflow_id)
        return jsonify(workflow or {})
    except Exception as e:
        return jsonify({}), 404

@workflow_bp.route('/api/save', methods=['POST'])
def api_save():
    try:
        data = request.json
        workflow_id = data.get('id')
        if save_sultan_object('workflows', workflow_id, data):
            return jsonify({"success": True})
        return jsonify({"error": "Failed to save workflow"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@workflow_bp.route('/api/delete/<workflow_id>', methods=['DELETE'])
def api_delete(workflow_id):
    try:
        delete_sultan_object('workflows', workflow_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
