import logging
from logging.handlers import TimedRotatingFileHandler
import os

# Define the logs directory within the app
logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
# Ensure logs directory exists
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s]: %(message)s")

# Configure the root logger manually
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Remove all existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
root_logger.addHandler(stream_handler)

# Create a TimedRotatingFileHandler when the workspace allows file writes.
log_filename = os.path.join(logs_dir, "app.log")
try:
    file_handler = TimedRotatingFileHandler(
        log_filename, when="midnight", interval=1, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
except OSError:
    root_logger.warning("File logging disabled because app.log is not writable: %s", log_filename)

# Main application logger
logger = logging.getLogger(__name__)


# Custom filter class to ensure log message only shows once
class OneTimeFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.has_run = False

    def filter(self, record):
        if not self.has_run:
            self.has_run = True
            return True
        return False


# Add SQLAlchemy pool logging configuration
sqlalchemy_pool_logger = logging.getLogger("sqlalchemy.pool")
sqlalchemy_pool_logger.setLevel(logging.DEBUG)

# # APScheduler logging configuration
# aps_logger_default = logging.getLogger('apscheduler.executors.default')
# aps_logger_default.addFilter(OneTimeFilter())
aps_logger_default = logging.getLogger("sqlalchemy.pool.impl.AsyncAdaptedQueuePool")
aps_logger_default.addFilter(OneTimeFilter())

# aps_logger_scheduler = logging.getLogger('apscheduler.scheduler')
# aps_logger_scheduler.addFilter(OneTimeFilter())
