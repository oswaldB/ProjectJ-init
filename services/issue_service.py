import logging
from main import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, remove_circular_references, CircularRefEncoder
import json
import os

logger = logging.getLogger(__name__)