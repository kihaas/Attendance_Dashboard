import logging
import os

from dotenv import load_dotenv

load_dotenv()
os.makedirs("data", exist_ok=True)

JOURNAL_USERNAME = os.getenv("JOURNAL_USERNAME", "")
JOURNAL_PASSWORD = os.getenv("JOURNAL_PASSWORD", "")
APPLICATION_KEY = os.getenv("APPLICATION_KEY", "")
REQUIRED_PERCENT = float(os.getenv("REQUIRED_ATTENDANCE_PERCENT", "60"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/attendance.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("data/app.log", encoding="utf-8")],
)