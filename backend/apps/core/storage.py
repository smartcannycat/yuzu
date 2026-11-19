"""Custom Django file storage backends."""

from django.core.files.storage import FileSystemStorage


class PrivateIntakeStorage(FileSystemStorage):
    """Filesystem storage that refuses public URL generation for private intake files."""

    @property
    def base_url(self) -> None:
        return None
