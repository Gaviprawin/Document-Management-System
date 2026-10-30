import os

from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address

load_dotenv()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv(
        "RATE_LIMIT_STORAGE_URI",
        "memory://",
    ),
)