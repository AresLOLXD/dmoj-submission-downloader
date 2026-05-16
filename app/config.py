import os
from dotenv import load_dotenv

load_dotenv()

DMOJ_BASE_URL: str = os.environ["DMOJ_BASE_URL"].rstrip("/")
DMOJ_API_TOKEN: str = os.environ["DMOJ_API_TOKEN"]
SECRET_KEY: str = os.environ["SECRET_KEY"]
HTTPS_ONLY: bool = os.environ.get("HTTPS_ONLY", "true").lower() != "false"
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
