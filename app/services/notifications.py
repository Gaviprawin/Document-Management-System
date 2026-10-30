import logging

logger = logging.getLogger(__name__)


def send_upload_notification(
    email: str,
    filename: str,
) -> None:
    logger.info(
        "UPLOAD_NOTIFICATION recipient=%s filename=%s",
        email,
        filename,
    )