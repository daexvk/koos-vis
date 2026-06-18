import secrets

from dotenv import load_dotenv
from fastapi import Header, HTTPException

from app.core.config import get_settings

load_dotenv()

def verify_api_key(x_api_key: str = Header(None)):
    api_key = get_settings().auth.api_key
    if not api_key or not x_api_key or not secrets.compare_digest(x_api_key, api_key):
        raise HTTPException(status_code=403, detail="Forbidden")
