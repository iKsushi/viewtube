"""Stream all objects to/from a tar archive; only used while application writes are stopped."""

import argparse
import io
import sys
import tarfile

from app.core.config import get_settings
from app.services.storage import ensure_bucket, s3


class ArchiveBody(io.RawIOBase):
    """S3 must not seek in a forward-only tar stream."""

    def __init__(self, stream):
        self.stream = stream

    def readable(self):
        return True

    def read(self, size=-1):
        return self.stream.read(size)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "import"])
    action = parser.parse_args().action
    bucket = get_settings().s3_bucket
    if action == "export":
        with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
            for page in s3().get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    response = s3().get_object(Bucket=bucket, Key=key)
                    entry = tarfile.TarInfo(key)
                    entry.size = response["ContentLength"]
                    entry.pax_headers = {
                        "viewtube.content_type": response.get(
                            "ContentType", "application/octet-stream"
                        )
                    }
                    try:
                        archive.addfile(entry, response["Body"])
                    finally:
                        response["Body"].close()
    else:
        ensure_bucket()
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
            for entry in archive:
                if (
                    not entry.isfile()
                    or not entry.name.startswith("videos/")
                    or ".." in entry.name.split("/")
                ):
                    raise ValueError("Unexpected object in media backup")
                file = archive.extractfile(entry)
                s3().upload_fileobj(
                    ArchiveBody(file),
                    bucket,
                    entry.name,
                    ExtraArgs={
                        "ContentType": entry.pax_headers.get(
                            "viewtube.content_type", "application/octet-stream"
                        )
                    },
                )


if __name__ == "__main__":
    main()
