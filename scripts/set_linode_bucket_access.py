#!/usr/bin/env python3
"""Set a Linode Object Storage bucket ACL without exposing the API token."""

import argparse
import configparser
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bucket")
    parser.add_argument("--region", default="us-ord")
    parser.add_argument("--acl", default="public-read")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".config" / "linode-cli",
    )
    args = parser.parse_args()

    config = configparser.ConfigParser()
    if not config.read(args.config):
        raise SystemExit(f"Linode CLI config not found: {args.config}")

    username = config["DEFAULT"].get("default-user", "").strip()
    if not username or username not in config:
        raise SystemExit("Linode CLI default user is not configured")

    token = config[username].get("token", "").strip()
    if not token:
        raise SystemExit("Linode CLI token is missing")

    url = (
        "https://api.linode.com/v4/object-storage/buckets/"
        f"{args.region}/{args.bucket}/access"
    )
    response = requests.put(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"acl": args.acl},
        timeout=30,
    )
    response.raise_for_status()
    print(f"Bucket {args.bucket} ACL set to {args.acl}")


if __name__ == "__main__":
    main()
