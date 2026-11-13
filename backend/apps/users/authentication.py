from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.exceptions import AuthenticationFailed, InvalidToken
from ninja_jwt.settings import api_settings


class AppJWTAuth(JWTAuth):
    """JWT authentication validating UUID user identifiers safely."""

    def get_user(self, validated_token) -> AbstractBaseUser:
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise InvalidToken(_("Token contained no recognizable user identification")) from exc

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except (ValueError, DjangoValidationError) as exc:
            raise InvalidToken(_("Token contained invalid user identification")) from exc
        except self.user_model.DoesNotExist as exc:
            raise AuthenticationFailed(_("User not found")) from exc

        if not user.is_active:
            raise AuthenticationFailed(_("User is inactive"))

        return user
