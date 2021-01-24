"""
API endpoints for nunaserver.
"""
import tempfile
import os
from pathlib import Path
import flask
from nunaserver import settings
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
def upload():
    """
    Handle uploaded DSDL namespace repository archives.
    This expects either an already made zip archive uploaded
    as a file or a URL link to a zip archive.

    Frontend converts GitHub links into zip archives.

    Takes multipart/form-data (obviously, because we have a file upload).
    """
    arch_dir = Path(tempfile.mkdtemp(prefix="pyuavcan-cli-dsdl"))

    try:
        form = UploadForm(flask.request.form, flask.request.files)
    except ValidationError as error:
        return flask.jsonify(error.errors)

    # TODO: Move this out to a celery task, maybe?
    # Might be difficult to move files out (only way is encode to b64 and
    # yeet it across redis = might run into RAM issues)
    # Could just move URL fetching
    for file in form.archive_files:
        # Create temp file for zip archive
        _, file_path = tempfile.mkstemp(".zip", "dsdl")

        # Save and unzip
        file.save(file_path)
        unzip_to_directory(file_path, arch_dir)

        # Delete zip file
        os.unlink(file_path)
    for url in form.archive_urls:
        fetch_remote_namespace(url, arch_dir)

    # Gather all the namespace directories
    inner = [d for d in Path(arch_dir).iterdir() if d.is_dir()]
    ns_dirs = []
    for path in inner:
        ns_dirs.extend(
            [d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]
        )

    out_dir = Path(tempfile.mkdtemp(prefix="nunavut-out"))

    # Generate nnvg command
    # pylint: disable=invalid-name
    command = ""
    for c, ns_dir in enumerate(ns_dirs):
        if c > 0:
            command += "\n"
        command += "nnvg "
        command += f"--target-language {form.target_lang} "
        if form.target_endian != "any":
            command += f"--target-endianness {form.target_endian} "
        command += f"{' '.join(form.flags)}"
        command += f" dsdl_src{str(ns_dir).replace(str(arch_dir), '')}"
        for lookup_dir in ns_dirs:
            if lookup_dir != ns_dir:
                command += (
                    f" --lookup dsdl_src{str(lookup_dir).replace(str(arch_dir), '')}"
                )

    task = generate_dsdl.delay(
        str(arch_dir),
        list(map(str, ns_dirs)),
        form.target_lang,
        form.target_endian,
        form.flags,
        str(out_dir),
    )

    return (
        flask.jsonify(
            {
                "command": command,
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
