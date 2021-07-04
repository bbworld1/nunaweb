"""
Global settings and constants read by Flask and other
parts of the server.
"""
import logging
import sys
import os

# Server version
SERVER_VERSION = os.environ.get("NUNASERVER_VERSION") or "v1.0.0"

# Settings for Flask
ALLOWED_EXTENSIONS = {"zip"}

# Minio instance
MINIO_URL = os.environ.get("NS_MINIO_URL") or "localhost:9000"
MINIO_RESULTS = os.environ.get("NS_MINIO_RESULTS") or "http://localhost:9000/results"
MINIO_ACCESS = os.environ.get("NS_MINIO_ACCESS_KEY") or None
MINIO_SECRET = os.environ.get("NS_MINIO_SECRET_KEY") or None
MINIO_SECURE = bool(os.environ.get("NS_MINIO_SECURE")) or False

# Rate limiting (set as needed)
# These defaults might be too high; not sure
UPLOAD_LIMITS = "200/day;20/minute"
UPLOAD_SIZE_MAX = 16 * 1024 * 1024  # 16 MB max
REMOTE_NS_SIZE_MAX = 4 * 1024 * 1024  # 8 MB max

# Celery
CELERY_RESULT_BACKEND = os.environ.get("NS_REDIS_RESULT") or "redis://localhost"
CELERY_BROKER_URL = os.environ.get("NS_REDIS_BROKER") or "redis://localhost:6379/0"

# Logging
LOG_FILE = os.environ.get("NS_LOG_FILE") or "stdout"
LOG_LEVEL = int(os.environ.get("NS_LOG_LEVEL") or logging.WARNING)

# CSRF
CSRF_SECRET_KEY = os.environ.get("CSRF_SECRET_KEY") or "123abc"

# CORs
CORS_ALLOWED_DOAMINS = os.environ.get("CORS_ALLOWED_DOMAINS") or "*"