import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN", "").strip()

# Parsed as a list to ensure order and support indexing for SUPER_ADMIN_ID
ADMIN_IDS = [
    int(item.strip())
    for item in os.getenv("ADMIN_IDS", "").split(",")
    if item.strip().isdigit()
]

SUPER_ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else None

if not API_TOKEN:
    raise RuntimeError("API_TOKEN is missing. Create a .env file using .env.example.")