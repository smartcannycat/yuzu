import pytest
from django.test import Client

from apps.users.models import User


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
