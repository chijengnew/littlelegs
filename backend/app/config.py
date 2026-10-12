import os

from dotenv import load_dotenv

load_dotenv()

AUTH_MODE = os.getenv("AUTH_MODE", "mock")
DB_MODE = os.getenv("DB_MODE", "memory")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]