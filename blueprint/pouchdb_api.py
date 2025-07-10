
from flask import Blueprint, jsonify, request
from services.pouchdb_service import pouchdb_sync_service
import logging

logger = logging.getLogger(__name__)

pouchdb_api_bp = Blueprint('pouchdb_api', __name__, url_prefix='/sultan/api/pouchdb')

@pouchdb_api_bp.route('/discover-sources', methods=['GET'])
def discover_sources():
    """Discover all available data sources"""
    try:
        sources = pouchdb_sync_service.discover_data_sources()
        return jsonify({
            'success': True,
            'sources': list(sources)
        })
    except Exception as e:
        logger.error(f"Failed to discover sources: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pouchdb_api_bp.route('/dashboard-sources/<dashboard_id>', methods=['GET'])
def get_dashboard_sources(dashboard_id):
    """Get data sources for a specific dashboard"""
    try:
        sources = pouchdb_sync_service.get_dashboard_sources(dashboard_id)
        return jsonify({
            'success': True,
            'sources': list(sources)
        })
    except Exception as e:
        logger.error(f"Failed to get dashboard sources: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pouchdb_api_bp.route('/sync-status', methods=['GET'])
def get_sync_status():
    """Get current sync status for all sources"""
    try:
        status = pouchdb_sync_service.get_sync_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pouchdb_api_bp.route('/sync-source/<source_id>', methods=['POST'])
def sync_source(source_id):
    """Manually trigger sync for a specific source"""
    try:
        # This would trigger the sync process
        pouchdb_sync_service.update_sync_status(source_id, 'pending', 0, 'Sync requested')
        
        return jsonify({
            'success': True,
            'message': f'Sync triggered for {source_id}'
        })
    except Exception as e:
        logger.error(f"Failed to trigger sync for {source_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pouchdb_api_bp.route('/source-info/<source_id>', methods=['GET'])
def get_source_info(source_id):
    """Get information about a data source"""
    try:
        count = pouchdb_sync_service.get_source_data_count(source_id)
        status = pouchdb_sync_service.get_sync_status().get(source_id, {})
        
        return jsonify({
            'success': True,
            'source_id': source_id,
            'record_count': count,
            'sync_status': status
        })
    except Exception as e:
        logger.error(f"Failed to get source info for {source_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
