import logging
from main import s3, BUCKET_NAME, LOCAL_BUCKET_DIR, CircularRefEncoder
import json
import os

logger = logging.getLogger(__name__)