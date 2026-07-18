#!/usr/bin/env python3
"""Inspect a Linode bucket policy using an existing rclone remote."""

import argparse
import configparser
import json
from pathlib import Path

import boto3
from botocore.config import Config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bucket")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--remote", default="linode-ord")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)
    remote = config[args.remote]
    client = boto3.client(
        "s3",
        endpoint_url=remote["endpoint"],
        aws_access_key_id=remote["access_key_id"],
        aws_secret_access_key=remote["secret_access_key"],
        config=Config(
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
    policy = json.loads(client.get_bucket_policy(Bucket=args.bucket)["Policy"])
    print(json.dumps(policy, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
