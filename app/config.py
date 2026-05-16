import os
from dotenv import load_dotenv

load_dotenv()

DMOJ_BASE_URL: str = os.environ["DMOJ_BASE_URL"].rstrip("/")
DMOJ_API_TOKEN: str = os.environ["DMOJ_API_TOKEN"]
SECRET_KEY: str = os.environ["SECRET_KEY"]
