from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from archive.importer import import_path
from archive.models import Collection


class Command(BaseCommand):
    help = "Safely import election release ZIP archives and PDFs."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--collection")

    def handle(self, path, collection=None, **options):
        source_path = Path(path)
        if not source_path.exists():
            raise CommandError(f"Import path does not exist: {path}")
        if collection and not Collection.objects.filter(slug=collection).exists():
            raise CommandError(f"Unknown collection slug: {collection}")
        run = import_path(source_path, collection)
        self.stdout.write(self.style.SUCCESS(
            f"Import {run.pk} complete: {run.files_imported} imported, "
            f"{run.duplicates} duplicates, {run.errors} errors."
        ))
