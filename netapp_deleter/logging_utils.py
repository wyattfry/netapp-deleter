"""
Logging utilities for the NetApp deleter.
"""

import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
RED = "\033[0;31m"
GRN = "\033[0;32m"
RST = "\033[0m"


def setup_logging(verbose):
    """Configure logging based on verbosity level"""
    if verbose:
        logger.setLevel(logging.DEBUG)
        # Enable Azure SDK debug logging
        logging.getLogger("azure").setLevel(logging.DEBUG)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
            logging.DEBUG
        )
    else:
        logger.setLevel(logging.INFO)
        # Silence Azure SDK debug logging
        logging.getLogger("azure").setLevel(logging.WARNING)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
            logging.WARNING
        )
        logging.getLogger("azure.identity").setLevel(logging.WARNING) 