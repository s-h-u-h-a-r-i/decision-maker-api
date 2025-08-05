import firebase_admin
from .settings import settings

firebase_app = firebase_admin.initialize_app(
    options={"projectId": settings.google_cloud_project}
)

__all__ = ["firebase_app"]
