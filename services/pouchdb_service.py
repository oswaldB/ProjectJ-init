
import logging
import json
from typing import Dict, List, Set
from services.s3_service import list_sultan_objects, get_sultan_object, list_folder_with_filter

logger = logging.getLogger(__name__)

class PouchDBSyncService:
    def __init__(self):
        self.sync_status = {}
        self.available_sources = set()
        
    def discover_data_sources(self) -> Set[str]:
        """Discover all available data sources from dashboards and forms"""
        sources = set()
        
        try:
            # Get all dashboards to find their data sources
            dashboards = list_sultan_objects('dashboards')
            for dashboard in dashboards:
                form_id = dashboard.get('form_id')
                source_id = dashboard.get('source_id')
                
                if form_id:
                    sources.add(form_id)
                if source_id and source_id != form_id:
                    sources.add(source_id)
                    
            # Get all forms as potential sources
            forms = list_sultan_objects('forms')
            for form in forms:
                form_id = form.get('id')
                if form_id:
                    sources.add(form_id)
                    
            # Add default jaffar issues source
            sources.add('issuesDB')
            
            self.available_sources = sources
            logger.info(f"Discovered data sources: {sources}")
            
        except Exception as e:
            logger.error(f"Failed to discover data sources: {e}")
            
        return sources
    
    def get_dashboard_sources(self, dashboard_id: str) -> Set[str]:
        """Get data sources used by a specific dashboard"""
        sources = set()
        
        try:
            dashboard = get_sultan_object('dashboards', dashboard_id)
            if dashboard:
                form_id = dashboard.get('form_id')
                source_id = dashboard.get('source_id')
                
                if form_id:
                    sources.add(form_id)
                if source_id and source_id != form_id:
                    sources.add(source_id)
                    
                # If no specific source, default to issuesDB
                if not sources:
                    sources.add('issuesDB')
                    
        except Exception as e:
            logger.error(f"Failed to get sources for dashboard {dashboard_id}: {e}")
            
        return sources
    
    def get_sync_status(self) -> Dict:
        """Get current sync status for all sources"""
        return self.sync_status.copy()
    
    def update_sync_status(self, source_id: str, status: str, progress: int = 0, message: str = ""):
        """Update sync status for a source"""
        self.sync_status[source_id] = {
            'status': status,  # 'pending', 'syncing', 'completed', 'error'
            'progress': progress,  # 0-100
            'message': message,
            'timestamp': json.dumps({"timestamp": "now"})  # Will be handled by frontend
        }
        logger.info(f"Sync status updated for {source_id}: {status} ({progress}%) - {message}")
    
    def get_source_data_count(self, source_id: str) -> int:
        """Get the number of records for a data source"""
        try:
            if source_id == 'issuesDB':
                # Count jaffar issues
                issues = list_folder_with_filter('jaffar/issues/')
                return len(issues)
            else:
                # Count form responses
                prefix = f'forms/{source_id}/submitted/'
                responses = list_folder_with_filter(prefix)
                return len(responses)
        except Exception as e:
            logger.error(f"Failed to count data for source {source_id}: {e}")
            return 0

# Global instance
pouchdb_sync_service = PouchDBSyncService()
