"""S3-class PathBackend with conditional PUT claim primitives (C1).

create-if-absent: ``PutObject`` + ``IfNoneMatch: "*"`` (412 = lost race).
replace-if-match: ``PutObject`` + ``IfMatch: <etag>`` (412 = lost race).
Whole-object PUT is already all-or-nothing (P3 on S3).

Listing is for discovery only — never a claim (C2).
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


def _client_error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        err = response.get("Error") or {}
        if isinstance(err, dict):
            code = err.get("Code")
            if code is not None:
                return str(code)
    return ""


def _is_precondition_failed(exc: BaseException) -> bool:
    code = _client_error_code(exc)
    return code in {
        "PreconditionFailed",
        "412",
        "ConditionalRequestConflict",
    }


class S3PathBackend:
    """PathBackend over an S3 bucket (or S3-compatible store).

    ``path`` arguments are object keys relative to optional ``prefix``.
    Pass an injected ``client`` (boto3 S3 client) for tests; otherwise
    constructs one via boto3 (optional dependency).
    """

    def __init__(
        self,
        bucket: str,
        *,
        client: Any = None,
        prefix: str = "",
    ) -> None:
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ImportError(
                    "S3PathBackend requires boto3. Install with: "
                    "pip install 'stations[s3]' or ensure boto3 is available."
                ) from exc
            client = boto3.client("s3")
        self.bucket = bucket
        self.client = client
        self.prefix = prefix.strip("/")

    def _key(self, path: str) -> str:
        path = path.lstrip("/")
        if not self.prefix:
            return path
        if not path:
            return self.prefix
        return f"{self.prefix}/{path}"

    def exists(self, path: str) -> bool:
        key = self._key(path)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            code = _client_error_code(exc)
            if code in {"404", "NoSuchKey", "NotFound", "404 Not Found"}:
                return False
            # botocore often uses 404 HTTP status without those codes
            response = getattr(exc, "response", None)
            if isinstance(response, dict):
                meta = response.get("ResponseMetadata") or {}
                if meta.get("HTTPStatusCode") == 404:
                    return False
            raise

    def read_bytes(self, path: str) -> bytes:
        key = self._key(path)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"]
        data: bytes = body.read()
        return data

    def etag(self, path: str) -> Optional[str]:
        """Server ETag for CAS (quoted or unquoted; normalized without quotes)."""
        key = self._key(path)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            code = _client_error_code(exc)
            response = getattr(exc, "response", None)
            status = None
            if isinstance(response, dict):
                status = (response.get("ResponseMetadata") or {}).get(
                    "HTTPStatusCode"
                )
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise
        raw = response.get("ETag")
        if raw is None:
            return None
        return str(raw).strip('"')

    def write_atomic(self, path: str, data: bytes) -> None:
        """Unconditional PUT (S3 single PUT is all-or-nothing)."""
        key = self._key(path)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def list(self, prefix: str) -> Iterator[str]:
        """Stream object keys under prefix (files only; no trailing-slash dirs).

        Paths are returned relative to the backend prefix (same as local root-rel).
        """
        key_prefix = self._key(prefix if prefix not in ("", ".") else "")
        if key_prefix and not key_prefix.endswith("/"):
            # list under this prefix as a "directory"
            list_prefix = key_prefix + "/"
        else:
            list_prefix = key_prefix

        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=list_prefix):
            for obj in page.get("Contents") or []:
                full_key = obj["Key"]
                if self.prefix:
                    rel = full_key[len(self.prefix) :].lstrip("/")
                else:
                    rel = full_key
                if rel:
                    yield rel

    def delete(self, path: str) -> None:
        key = self._key(path)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def create_if_absent(self, path: str, data: bytes) -> bool:
        """Test-and-set via IfNoneMatch='*' (C1). True on create; False on 412."""
        key = self._key(path)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                IfNoneMatch="*",
            )
            return True
        except Exception as exc:
            if _is_precondition_failed(exc):
                return False
            # Some older endpoints reject IfNoneMatch entirely
            code = _client_error_code(exc)
            if code in {"InvalidArgument", "NotImplemented"}:
                logger.warning(
                    "S3 create_if_absent: conditional PUT unsupported (%s)", code
                )
            raise

    def replace_if_match(
        self, path: str, data: bytes, *, etag: Optional[str]
    ) -> bool:
        """CAS replace via IfMatch (C1, C3). False on precondition failure."""
        key = self._key(path)
        if etag is None:
            # Unconditional replace (still a single PUT)
            self.write_atomic(path, data)
            return True
        # S3 expects quoted ETag in If-Match in some implementations; boto3
        # accepts both. Pass without quotes; botocore normalizes.
        match_value = etag.strip('"')
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                IfMatch=match_value,
            )
            return True
        except Exception as exc:
            if _is_precondition_failed(exc):
                return False
            raise
