
from flask import Blueprint, render_template, request, jsonify
import logging
from services.s3_service import (
    list_sultan_objects,
    get_sultan_object,
    save_sultan_object,
    delete_sultan_object
)

logger = logging.getLogger(__name__)

# Create Agents blueprint with prefix
agents_bp = Blueprint('agents', __name__, url_prefix='/pc-analytics-jaffar/sultan/agents')

@agents_bp.route('/')
def index():
    """List all agents"""
    return render_template('sultan/agents/index.html')

@agents_bp.route('/edit/<agent_id>')
def edit(agent_id):
    """Edit a specific agent"""
    return render_template('sultan/agents/edit.html', agent_id=agent_id)

@agents_bp.route('/chat')
def chat():
    """Chat interface with agent selection"""
    return render_template('sultan/agents/chat.html')

# API Routes
@agents_bp.route('/api/list')
def api_list():
    """Get list of all agents"""
    try:
        agents = list_sultan_objects('agents')
        return jsonify(agents)
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return jsonify({"error": str(e)}), 500

@agents_bp.route('/api/<agent_id>')
def api_get(agent_id):
    """Get a specific agent by ID"""
    try:
        agent = get_sultan_object('agents', agent_id)
        if agent:
            return jsonify(agent)
        else:
            return jsonify({"error": "Agent not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {e}")
        return jsonify({"error": str(e)}), 500

@agents_bp.route('/api/save', methods=['POST'])
def api_save():
    """Save or update an agent"""
    try:
        data = request.json
        agent_id = data.get('id')
        
        if not agent_id:
            return jsonify({"error": "Agent ID is required"}), 400
            
        # Ensure required fields
        agent_data = {
            'id': agent_id,
            'name': data.get('name', agent_id),
            'description': data.get('description', ''),
            'prompt': data.get('prompt', ''),
            'model': data.get('model', 'gpt-3.5-turbo'),
            'temperature': data.get('temperature', 0.7),
            'max_tokens': data.get('max_tokens', 1000),
            'system_message': data.get('system_message', ''),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at')
        }
        
        save_sultan_object('agents', agent_id, agent_data)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to save agent: {e}")
        return jsonify({"error": str(e)}), 500

@agents_bp.route('/api/delete/<agent_id>', methods=['DELETE'])
def api_delete(agent_id):
    """Delete an agent"""
    try:
        delete_sultan_object('agents', agent_id)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete agent {agent_id}: {e}")
        return jsonify({"error": str(e)}), 500

@agents_bp.route('/api/chat', methods=['POST'])
def api_chat():
    """Chat with a specific agent"""
    try:
        data = request.json
        agent_id = data.get('agent_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])
        
        if not agent_id or not message:
            return jsonify({"error": "Agent ID and message are required"}), 400
            
        # Get agent configuration
        agent = get_sultan_object('agents', agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404
            
        # TODO: Implement actual AI chat logic here
        # For now, return a simple response
        response = {
            "agent_id": agent_id,
            "agent_name": agent.get('name', agent_id),
            "message": f"Response from {agent.get('name', agent_id)}: I received your message '{message}'",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Failed to process chat: {e}")
        return jsonify({"error": str(e)}), 500
