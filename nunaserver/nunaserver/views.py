"""
API endpoints for nunaserver.
"""
import tempfile
import os
import uuid
from pathlib import Path
import flask
from minio.commonconfig import Filter, ENABLED
from minio.lifecycleconfig import LifecycleConfig, Expiration, Rule
from nunaserver import settings
from nunaserver.minio_connection import storage
from nunaserver.limiter import limiter
from nunaserver.utils.archive_utils import fetch_remote_namespace, unzip_to_directory
from nunaserver.generator import generate_dsdl
from nunaserver.forms import UploadForm, ValidationError

api = flask.Blueprint("api", __name__)


@api.route("/", methods=["GET"])
def root():
    """
    Return 200 OK status with some server information.
    """
    return f"Nunaserver {settings.SERVER_VERSION}"


# pylint: disable=invalid-name,too-many-locals
@api.route("/upload", methods=["POST"])
@limiter.limit(settings.UPLOAD_LIMITS)
def upload():
    """
    Handle uploaded DSDL namespace repository archives.
    This expects either an already made zip archive uploaded
    as a file or a URL link to a zip archive.

    Frontend converts GitHub links into zip archives.

    Takes multipart/form-data (obviously, because we have a file upload).
    """
    build_uuid = str(uuid.uuid4())
    storage.make_bucket(build_uuid)
    config = LifecycleConfig(
        [
            Rule(
                ENABLED,
                rule_filter=Filter(prefix="uploads/"),
                rule_id=f"delete_rule_{build_uuid}",
                expiration=Expiration(days=30),
            ),
        ],
    )
    storage.set_bucket_lifecycle(build_uuid, config)

    try:
        form = UploadForm(flask.request.form, flask.request.files)
    except ValidationError as error:
        return flask.jsonify(error.errors), 400

    for file in form.archive_files:
        size = os.fstat(file.fileno()).st_size
        storage.put_object(build_uuid, f"uploads/{file.filename}", file, size)

    # Kick off Celery task to generate DSDL
    task = generate_dsdl.delay(
        build_uuid,
        form.archive_urls,
        form.target_lang,
        form.target_endian,
        form.flags,
    )

    return (
        flask.jsonify(
            {
                "task_url": flask.url_for("api.taskstatus", task_id=task.id),
            }
        ),
        202,
    )


@api.route("/status/<task_id>")
def taskstatus(task_id):
    """
    Fetch the status of a running generation task.
    """
    try:
        task = generate_dsdl.AsyncResult(task_id)
        if task.state == "PENDING":
            # job did not start yet
            response = {
                "state": task.state,
                "current": 0,
                "total": 1,
                "status": "Pending...",
            }
        elif task.state != "FAILURE":
            response = {
                "state": task.state,
                "current": task.info.get("current", 0),
                "total": task.info.get("total", 1),
                "status": task.info.get("status", ""),
                "command": task.info.get("command", ""),
            }
            if "result" in task.info:
                response["result"] = task.info["result"]
        else:
            # something went wrong in the background job
            response = {
                "state": task.state,
                "current": 1,
                "total": 1,
                "status": str(task.info),  # this is the exception raised
            }
        return flask.jsonify(response)
    except AttributeError:
        return flask.jsonify(
            {
                "state": "CANCELED",
                "current": "0",
                "total": "1",
                "status": "Task was canceled.",
            }
        )


@api.route("/status/<task_id>/cancel")
def taskcancel(task_id):
    """
    Cancel a running generation task.
    """
    task = generate_dsdl.AsyncResult(task_id)
    task.revoke(terminate=True)

    return flask.jsonify({"response": "OK"}), 200

@api.route("/health")
def health_check():
    """
        standard health check endpoint
        currently no dependency is being health checked
        but if there is any future dependency health check needs, simply add the code here
    """
    return flask.jsonify({"status": "healthy"}), 200