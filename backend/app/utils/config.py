import os

from dotenv import load_dotenv

load_dotenv()


def get_cors_origins() -> list[str]:
    default = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://pos-cafeteria-brown.vercel.app,"
        "https://localhost,"
        "http://localhost,"
        "capacitor://localhost"
    )
    raw = os.getenv("CORS_ORIGINS", default)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"
