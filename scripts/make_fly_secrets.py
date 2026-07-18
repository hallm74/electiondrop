#!/usr/bin/env python3
"""Create a private Fly secrets file from the local Object Storage env."""

import argparse
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("storage_env", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    storage_values = args.storage_env.read_text().rstrip()
    django_secret = secrets.token_urlsafe(48)
    args.output.write_text(
        f"{storage_values}\nDJANGO_SECRET_KEY={django_secret}\n"
    )
    args.output.chmod(0o600)


if __name__ == "__main__":
    main()
