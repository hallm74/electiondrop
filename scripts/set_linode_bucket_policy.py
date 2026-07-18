#!/usr/bin/env python3
"""Apply a public-read policy to one prefix in a Linode S3 bucket."""

import argparse
import configparser
import json
from pathlib import Path

import boto3
from botocore.config import Config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bucket")
    parser.add_argument("key_json", type=Path, nargs="?")
    parser.add_argument("--linode-cli-config", type=Path)
    parser.add_argument("--rclone-config", type=Path)
    parser.add_argument("--remote", default="linode-ord")
    parser.add_argument("--prefix", default="media/")
    parser.add_argument(
        "--endpoint",
        default="https://us-ord-10.linodeobjects.com",
    )
    args = parser.parse_args()

    if args.rclone_config:
        rclone_config = configparser.ConfigParser()
        if not rclone_config.read(args.rclone_config):
            raise SystemExit("rclone config could not be read")
        if args.remote not in rclone_config:
            raise SystemExit(f"rclone remote not found: {args.remote}")
        key_data = {
            "access_key": rclone_config[args.remote]["access_key_id"].strip(),
            "secret_key": rclone_config[args.remote]["secret_access_key"].strip(),
        }
    elif args.linode_cli_config:
        cli_config = configparser.ConfigParser()
        if not cli_config.read(args.linode_cli_config):
            raise SystemExit("Linode CLI config could not be read")
        username = cli_config["DEFAULT"]["default-user"].strip()
        key_data = {
            "access_key": cli_config[username]["plugin-obj-access-key"].strip(),
            "secret_key": cli_config[username]["plugin-obj-secret-key"].strip(),
        }
    elif args.key_json:
        key_data = json.loads(args.key_json.read_text())
        if isinstance(key_data, list):
            key_data = key_data[0]
    else:
        raise SystemExit("Provide key_json or --linode-cli-config")

    client = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=key_data["access_key"],
        aws_secret_access_key=key_data["secret_key"],
        config=Config(
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadArchiveMedia",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [
                    f"arn:aws:s3:::{args.bucket}/{args.prefix.lstrip('/')}*"
                ],
            }
        ],
    }
    client.put_bucket_policy(Bucket=args.bucket, Policy=json.dumps(policy))
    print(f"Public read policy applied to {args.bucket}/{args.prefix}")


if __name__ == "__main__":
    main()
