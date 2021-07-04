"""
Main Flask server configuration and startup.
"""
import sys
import os
import json
import logging
from pathlib import Path
import flask
from flask_cors import CORS
from flask_seasurf import SeaSurf
from flask_talisman import Talisman
from minio.commonconfig import Filter, ENABLED
from minio.lifecycleconfig import LifecycleConfig, Expiration, Rule
from nunaserver import settings
from nunaserver.minio_connection import storage
from nunaserver.limiter import limiter
from nunaserver.logging import init_logging
from nunaserver.views import api
from nunaserver.tasks import celery, init_celery

app = flask.Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = settings.UPLOAD_SIZE_MAX
app.config["MINIO_ENDPOINT"] = settings.MINIO_URL
app.config["MINIO_ACCESS_KEY"] = settings.MINIO_ACCESS
app.config["MINIO_SECRET_KEY"] = settings.MINIO_SECRET
app.config["MINIO_SECURE"] = settings.MINIO_SECURE

limiter.init_app(app)

CORS(app, resources = {
    r"/": {
        "origins": settings.CORS_ALLOWED_DOMAINS
    }
})

app.secret_key = settings.CSRF_SECRET_KEY
csrf = SeaSurf(app)

SELF = "'self'"
talisman = Talisman(
    app,
    content_security_policy = {
        'default-src': SELF
    }
)
# Setup celery
init_celery(celery, app)

# Setup logging
init_logging()

# Setup minio result bucket
# and set public access
if not storage.bucket_exists("results"):
    storage.make_bucket("results")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::results/*",
            },
        ],
    }
    storage.set_bucket_policy("results", json.dumps(policy))

    config = LifecycleConfig(
        [
            Rule(
                ENABLED,
                rule_filter=Filter(prefix="*"),
                rule_id="delete_rule_results",
                expiration=Expiration(days=30),
            ),
        ],
    )
    storage.set_bucket_lifecycle("results", config)

app.register_blueprint(api)

if __name__ == "__main__":
    app.run(port=5000)  # Dev server
