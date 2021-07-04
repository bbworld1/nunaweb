import logging
import os, sys, time
from nunaserver import settings

log_file = None


def init_logging():
    # Setup logging
    global log_file

    if log_file:
        return

    if settings.LOG_FILE == "stderr":
        log_file = sys.stderr
    elif settings.LOG_FILE == "stdout":
        log_file = sys.stdout
    else:
        log_file = settings.LOG_FILE
    if settings.LOG_FILE == "stdout" or settings.LOG_FILE == "stderr":
        log_handler = logging.StreamHandler(log_file)
    else:
        log_handler = logging.FileHandler(log_file)
    loggers = [logging.getLogger()]
    loggers = loggers + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]
    for logger in loggers:
        logger.setLevel(settings.LOG_LEVEL)
        logger.addHandler(log_handler)
