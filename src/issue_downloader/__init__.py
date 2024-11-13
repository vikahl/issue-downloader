"""issue-downloader

Downloads issues to Markdown files
"""

import logging

# Set up formatting for module logger
logger = logging.getLogger(__name__)

# Add handler to format messages
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
