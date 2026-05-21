from functools import lru_cache

from google.oauth2 import service_account

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


@lru_cache(maxsize=1)
def get_google_credentials() -> service_account.Credentials:
    from app.config import get_settings
    settings = get_settings()
    return service_account.Credentials.from_service_account_file(
        settings.google_service_account_path,
        scopes=_SCOPES,
    )
