from collections.abc import Generator
from copy import deepcopy

import pytest
from django.core.files.storage import default_storage, storages
from django.test import Client
from django.utils.functional import empty

from apps.lots.models import BatchItem
from apps.users.models import User


def _reset_storages() -> None:
    storages.__dict__.pop("backends", None)
    storages._backends = None
    storages._storages = {}
    default_storage._wrapped = empty
    BatchItem._meta.get_field("original_file").storage = storages["private_intake"]


@pytest.fixture(autouse=True)
def _isolated_media_root(tmp_path, settings) -> Generator[None, None, None]:
    """Keep uploaded/starter media and private intake files inside pytest's temporary directory."""
    media_dir = tmp_path / "media"
    private_intake_dir = tmp_path / "private_intake"
    media_dir.mkdir(parents=True, exist_ok=True)
    private_intake_dir.mkdir(parents=True, exist_ok=True)

    settings.MEDIA_ROOT = str(media_dir)
    settings.PRIVATE_INTAKE_ROOT = str(private_intake_dir)
    updated_storages = deepcopy(settings.STORAGES)
    updated_storages["default"]["OPTIONS"] = {
        **updated_storages["default"].get("OPTIONS", {}),
        "location": str(media_dir),
    }
    updated_storages["private_intake"]["OPTIONS"] = {
        **updated_storages["private_intake"].get("OPTIONS", {}),
        "location": str(private_intake_dir),
        "base_url": None,
    }
    settings.STORAGES = updated_storages
    settings.RATE_LIMIT_ENABLED = False
    _reset_storages()
    yield
    _reset_storages()


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
