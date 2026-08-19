#!/usr/bin/env python3
"""Zero-install client for the MiniMax H3 Ref2VA LAN service."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import mimetypes
import os
import ssl
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping
from urllib.parse import quote, urlsplit


SUPPORTED_PROTOCOL_MAJOR = 1
RESET_LISTENER_PORT = 8192
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


class ClientError(RuntimeError):
    """A safe, actionable client or server contract failure."""


@dataclass(frozen=True)
class ClientConfig:
    api_url: str
    token: str | None = None


@dataclass
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: Any = b""
    close_callback: Callable[[], None] | None = None

    def close(self) -> None:
        body_close = getattr(self.body, "close", None)
        if callable(body_close):
            body_close()
        if self.close_callback is not None:
            self.close_callback()
            self.close_callback = None


def _config_from_file(path: Path) -> ClientConfig | None:
    if not path.is_file():
        return None
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ClientError(f"token config must have mode 0600: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClientError(f"cannot read config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ClientError(f"config must contain a JSON object: {path}")
    api = value.get("api", value.get("api_url"))
    token = value.get("token")
    if api is not None and not isinstance(api, str):
        raise ClientError(f"config api must be a string: {path}")
    if token is not None and not isinstance(token, str):
        raise ClientError(f"config token must be a string: {path}")
    return ClientConfig((api or "http://127.0.0.1:8191").rstrip("/"), token)


def load_config(*, env: Mapping[str, str] | None = None, home: Path | None = None) -> ClientConfig:
    values = os.environ if env is None else env
    root = Path.home() if home is None else Path(home)
    environment_api = values.get("MINIMAX_H3_API")
    environment_token = values.get("MINIMAX_H3_TOKEN")
    if environment_api and environment_token:
        return ClientConfig(environment_api.rstrip("/"), environment_token)
    file_config = (
        _config_from_file(root / ".config" / "minimax-h3" / "config.json")
        or ClientConfig("http://127.0.0.1:8191", None)
    )
    api = environment_api or file_config.api_url
    token = environment_token or file_config.token
    return ClientConfig(api.rstrip("/"), token)


class HttpTransport:
    def __init__(self, api_url: str, *, timeout: float = 60.0):
        parsed = urlsplit(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ClientError(f"invalid API URL: {api_url}")
        if parsed.query or parsed.fragment:
            raise ClientError("API URL cannot contain a query or fragment")
        self.scheme = parsed.scheme
        self.host = parsed.hostname
        self.port = parsed.port
        self.base_path = parsed.path.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, *, headers=None, data=None) -> HttpResponse:
        connection_class = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.scheme == "https":
            kwargs["context"] = ssl.create_default_context()
        connection = connection_class(self.host, self.port, **kwargs)
        target = self.base_path + (path if path.startswith("/") else "/" + path)
        request_headers = dict(headers or {})
        try:
            connection.putrequest(method, target)
            for name, value in request_headers.items():
                connection.putheader(name, str(value))
            connection.endheaders()
            if data is not None:
                if hasattr(data, "read"):
                    while True:
                        chunk = data.read(1024 * 1024)
                        if not chunk:
                            break
                        connection.send(chunk)
                else:
                    connection.send(data)
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            connection.close()
            raise ClientError(f"request failed: {method} {path}: {exc}") from exc
        return HttpResponse(
            status=response.status,
            headers={name: value for name, value in response.getheaders()},
            body=response,
            close_callback=connection.close,
        )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _read_all(response: HttpResponse) -> bytes:
    try:
        if isinstance(response.body, bytes):
            return response.body
        return response.body.read()
    finally:
        response.close()


def _error_message(response: HttpResponse) -> str:
    raw = _read_all(response)
    try:
        value = json.loads(raw.decode("utf-8"))
        error = value.get("error", value) if isinstance(value, dict) else value
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if code and message:
                return f"{code}: {message}"
            if message:
                return str(message)
    except (UnicodeError, json.JSONDecodeError):
        pass
    return raw.decode("utf-8", errors="replace")[:500] or f"HTTP {response.status}"


class H3Client:
    def __init__(self, config: ClientConfig, *, transport=None):
        self.config = config
        self.transport = transport or HttpTransport(config.api_url)

    def _request(self, method: str, path: str, *, headers=None, data=None, expected=(200,)) -> HttpResponse:
        request_headers = dict(headers or {})
        if self.config.token:
            request_headers["Authorization"] = f"Bearer {self.config.token}"
        response = self.transport.request(method, path, headers=request_headers, data=data)
        if response.status not in expected:
            message = _error_message(response)
            raise ClientError(f"{method} {path} returned HTTP {response.status}: {message}")
        return response

    def _json(self, method: str, path: str, *, value=None, expected=(200,)) -> dict[str, Any]:
        headers: dict[str, str] = {"Accept": "application/json"}
        data = None
        if value is not None:
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))
        response = self._request(method, path, headers=headers, data=data, expected=expected)
        raw = _read_all(response)
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ClientError(f"server returned invalid JSON for {path}") from exc
        if not isinstance(result, dict):
            raise ClientError(f"server returned a non-object JSON response for {path}")
        return result

    def doctor(self) -> dict[str, Any]:
        live = self._json("GET", "/health/live")
        ready = self._json("GET", "/health/ready")
        schema = self.schema()
        return {"live": live, "ready": ready, "schema": schema}

    def reset(self, *, wait_seconds: float = 300.0, poll_interval: float = 10.0) -> dict[str, Any]:
        """Out-of-band API restart via the reset listener on port 8192.

        Covers the failure classes the main port cannot report on itself: a
        poisoned worker (readiness 503 `worker: cuda_poisoned`) and a wedged
        API process (TCP connects, every request hangs). The listener is a
        separate process on the host, restarts only the API task, and refuses
        repeat resets inside a 300-second cooldown.
        """
        reset_transport = HttpTransport(
            f"{self.transport.scheme}://{self.transport.host}:{RESET_LISTENER_PORT}",
            timeout=30.0,
        )
        headers = {"Accept": "application/json"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        try:
            response = reset_transport.request("POST", "/reset", headers=headers)
        except ClientError as exc:
            raise ClientError(
                f"reset listener unreachable on port {RESET_LISTENER_PORT} - if the main "
                "API answers, the problem is probably the network path, which a reset "
                f"cannot fix: {exc}"
            ) from exc
        raw = _read_all(response)
        if response.status == 429:
            raise ClientError("reset refused: cooldown active, a restart was already issued recently")
        if response.status != 202:
            raise ClientError(f"reset returned HTTP {response.status}: {raw.decode('utf-8', 'replace')[:300]}")
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            try:
                ready = self._json("GET", "/health/ready")
            except ClientError:
                continue
            if ready.get("status") == "ready":
                return {"status": "recovered", "ready": ready}
        return {"status": "restart_issued_not_yet_ready", "waited_seconds": wait_seconds}

    def schema(self) -> dict[str, Any]:
        value = self._json("GET", "/v1/h3/schema")
        version = value.get("protocol_version")
        try:
            major = int(str(version).split(".", 1)[0])
        except (TypeError, ValueError) as exc:
            raise ClientError(f"invalid protocol version: {version!r}") from exc
        if major != SUPPORTED_PROTOCOL_MAJOR:
            raise ClientError(
                f"unsupported protocol major {major}; client supports {SUPPORTED_PROTOCOL_MAJOR}.x"
            )
        return value

    def upload(self, source: str | Path, media_type: str | None = None) -> str:
        path = Path(source)
        if not path.is_file():
            raise ClientError(f"upload source is not a file: {path}")
        hasher = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                size += len(chunk)
        digest = hasher.hexdigest()
        blob_id = f"sha256:{digest}"
        present = self.transport.request(
            "HEAD",
            f"/v1/blobs/{digest}",
            headers={"Authorization": f"Bearer {self.config.token}"} if self.config.token else {},
        )
        if present.status == 200:
            present.close()
            return blob_id
        if present.status != 404:
            message = _error_message(present)
            raise ClientError(f"HEAD /v1/blobs/{digest} returned HTTP {present.status}: {message}")
        present.close()
        content_type = media_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        headers = {
            "X-Blob-Sha256": blob_id,
            "Content-Length": str(size),
            "Content-Type": content_type,
        }
        with path.open("rb") as stream:
            response = self._request("POST", "/v1/blobs", headers=headers, data=stream, expected=(200, 201))
            value = json.loads(_read_all(response).decode("utf-8"))
        if isinstance(value, dict) and value.get("blob_id", blob_id) != blob_id:
            raise ClientError("server returned a different blob digest after upload")
        return blob_id

    def _materialize_local_inputs(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        result = json.loads(json.dumps(manifest, ensure_ascii=False, allow_nan=False))
        local = result.pop("local_inputs", None)
        if local is None:
            result.setdefault("cache_policy", "use")
            return result
        if "inputs" in result:
            raise ClientError("submission cannot contain both inputs and local_inputs")
        if not isinstance(local, dict):
            raise ClientError("local_inputs must be an object")
        unknown = set(local) - {"reference_images", "reference_videos", "reference_audios"}
        if unknown:
            raise ClientError("unknown local_inputs fields: " + ", ".join(sorted(unknown)))
        inputs: dict[str, Any] = {
            "reference_images": [self.upload(path) for path in local.get("reference_images", [])],
            "reference_videos": [],
            "reference_audios": [self.upload(path) for path in local.get("reference_audios", [])],
        }
        for item in local.get("reference_videos", []):
            if not isinstance(item, dict) or "video" not in item:
                raise ClientError("each local reference video needs a video path")
            paired = {"video": self.upload(item["video"])}
            if item.get("audio") is not None:
                paired["audio"] = self.upload(item["audio"])
            inputs["reference_videos"].append(paired)
        result["inputs"] = inputs
        result.setdefault("cache_policy", "use")
        return result

    def submit(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        payload = self._materialize_local_inputs(manifest)
        return self._json("POST", "/v1/h3/submissions", value=payload, expected=(200, 201, 202))

    def status(self, handle_id: str) -> dict[str, Any]:
        return self._json("GET", f"/v1/h3/submissions/{quote(handle_id, safe='')}")

    def attempt(self, attempt_id: str) -> dict[str, Any]:
        return self._json("GET", f"/v1/h3/attempts/{quote(attempt_id, safe='')}")

    def wait(
        self,
        handle_id: str,
        *,
        poll_interval: float = 20.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> dict[str, Any]:
        if poll_interval <= 0:
            raise ClientError("poll interval must be positive")
        while True:
            value = self.status(handle_id)
            if value.get("state") in TERMINAL_STATES:
                return value
            sleep(poll_interval)

    def cancel(self, handle_id: str) -> dict[str, Any]:
        path = f"/v1/h3/submissions/{quote(handle_id, safe='')}/cancel"
        return self._json("POST", path, value={})

    def download(self, artifact: Mapping[str, Any], destination: str | Path) -> Path:
        artifact_id = artifact.get("artifact_id")
        expected_size = artifact.get("size")
        expected_sha256 = artifact.get("sha256")
        expected_etag = artifact.get("etag")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ClientError("artifact document is missing artifact_id")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ClientError("artifact document is missing a valid size")
        if not isinstance(expected_sha256, str) or not expected_sha256.startswith("sha256:"):
            raise ClientError("artifact document is missing a valid sha256")
        if not isinstance(expected_etag, str) or not expected_etag:
            raise ClientError("artifact document is missing an etag")
        target = Path(destination)
        if target.exists():
            raise ClientError(f"download destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        if part.exists():
            part.unlink()
        response = self._request("GET", f"/v1/artifacts/{quote(artifact_id, safe='')}")
        try:
            header_size = _header(response.headers, "Content-Length")
            header_sha = _header(response.headers, "X-Content-SHA256")
            header_etag = _header(response.headers, "ETag")
            if header_size != str(expected_size):
                raise ClientError("download Content-Length does not match artifact document")
            if header_sha != expected_sha256:
                raise ClientError("download SHA-256 header does not match artifact document")
            if header_etag != expected_etag:
                raise ClientError("download ETag does not match artifact document")
            hasher = hashlib.sha256()
            written = 0
            with part.open("xb") as stream:
                if isinstance(response.body, bytes):
                    chunks = (response.body,)
                else:
                    chunks = iter(lambda: response.body.read(1024 * 1024), b"")
                for chunk in chunks:
                    stream.write(chunk)
                    hasher.update(chunk)
                    written += len(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if written != expected_size:
                raise ClientError("download byte count does not match artifact document")
            actual = "sha256:" + hasher.hexdigest()
            if actual != expected_sha256:
                raise ClientError("download SHA-256 does not match artifact document")
            os.replace(part, target)
            return target
        except Exception:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        finally:
            response.close()


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClientError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ClientError(f"JSON must contain an object: {path}")
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MiniMax H3 Ref2VA LAN client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check liveness, readiness, and protocol compatibility")
    commands.add_parser("schema", help="print the authoritative live model surface")
    upload = commands.add_parser("upload", help="upload or reuse one immutable input blob")
    upload.add_argument("path")
    upload.add_argument("--media-type")
    submit = commands.add_parser("submit", help="upload local inputs and submit one manifest")
    submit.add_argument("manifest")
    submit.add_argument("--refresh", action="store_true", help="explicitly replace a cached successful attempt")
    for name, help_text in (("status", "read a durable submission handle"), ("wait", "poll a handle to a terminal state"), ("cancel", "cancel this handle's interest")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("handle_id")
        if name == "wait":
            command.add_argument("--poll-interval", type=float, default=20.0)
    download = commands.add_parser("download", help="download one verified artifact from a successful handle")
    download.add_argument("handle_id")
    download.add_argument("kind", choices=("video", "mask"))
    download.add_argument("destination")
    reset = commands.add_parser("reset", help="out-of-band API restart when the service is poisoned or wedged")
    reset.add_argument("--wait-seconds", type=float, default=300.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = H3Client(load_config())
    if args.command == "doctor":
        result = client.doctor()
    elif args.command == "schema":
        result = client.schema()
    elif args.command == "upload":
        result = {"blob_id": client.upload(args.path, args.media_type)}
    elif args.command == "submit":
        manifest = _load_json(args.manifest)
        if args.refresh:
            manifest["cache_policy"] = "refresh"
        result = client.submit(manifest)
    elif args.command == "status":
        result = client.status(args.handle_id)
    elif args.command == "wait":
        result = client.wait(args.handle_id, poll_interval=args.poll_interval)
    elif args.command == "cancel":
        result = client.cancel(args.handle_id)
    elif args.command == "download":
        status = client.status(args.handle_id)
        artifacts = [item for item in status.get("artifacts", []) if item.get("kind") == args.kind]
        if len(artifacts) != 1:
            raise ClientError(f"expected exactly one {args.kind} artifact on handle {args.handle_id}")
        path = client.download(artifacts[0], args.destination)
        result = {"path": str(path), "artifact": artifacts[0]}
    elif args.command == "reset":
        result = client.reset(wait_seconds=args.wait_seconds)
    else:
        raise AssertionError(args.command)
    _print_json(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
