import pytest
from django.test import Client

from apps.users.models import User


@pytest.fixture(autouse=True)
def _isolated_media_root(tmp_path, settings) -> None:
    """Keep uploaded/starter media files inside pytest's temporary directory."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    settings.MEDIA_ROOT = str(media_dir)
    settings.RATE_LIMIT_ENABLED = False


@pytest.fixture
def api_client() -> Client:
    return Client()


@pytest.fixture
def user_factory(db):
    def create_user(
        email: str = "alex@example.com",
        password: str = "StrongPass123!",
        name: str | None = "Алексей",
        is_active: bool = True,
    ) -> User:
        return User.objects.create_user(
            email=email,
            password=password,
            name=name,
            is_active=is_active,
        )

    return create_user
