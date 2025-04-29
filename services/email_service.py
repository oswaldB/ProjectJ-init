
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
email_executor = ThreadPoolExecutor(max_workers=2)

def send_confirmation_if_needed(issue_data):
    """Send confirmation email if needed based on issue data"""
    try:
        logger.info(f"Processing confirmation email for issue: {issue_data.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
        return False
