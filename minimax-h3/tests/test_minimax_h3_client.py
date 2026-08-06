from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "minimax_h3_client.py"
SPEC = importlib.util.spec_from_file_location("minimax_h3_client", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
client_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = client_module
SPEC.loader.exec_module(client_module)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, path, *, headers=None, data=None):
        body = data.read() if hasattr(data, "read") else data
        self.requests.append((method, path, dict(headers or {}), body))
        response = self.responses.pop(0)
        return client_module.HttpResponse(
            status=response.get("status", 200),
            headers=response.get("headers", {}),
            body=response.get("body", b""),
        )


def json_response(value, status=200, headers=None):
    return {
        "status": status,
        "headers": {"Content-Type": "application/json", **(headers or {})},
        "body": json.dumps(value).encode(),
    }


def make_client(responses):
    transport = FakeTransport(responses)
    config = client_module.ClientConfig("http://h3.test:8191", "secret")
    return client_module.H3Client(config, transport=transport), transport


def test_generic_environment_beats_legacy_environment(tmp_path):
    env = {
        "MINIMAX_H3_API": "http://new.example:8191/",
        "MINIMAX_H3_TOKEN": "new-token",
        "COMMITTED_H3_API": "http://legacy.example:8191",
        "COMMITTED_H3_TOKEN": "legacy-token",
    }

    config = client_module.load_config(env=env, home=tmp_path)

    assert config.api_url == "http://new.example:8191"
    assert config.token == "new-token"


def test_complete_environment_does_not_read_stale_config(tmp_path):
    stale = tmp_path / ".config" / "minimax-h3" / "config.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("not json")

    config = client_module.load_config(
        env={"MINIMAX_H3_API": "http://env", "MINIMAX_H3_TOKEN": "env-token"},
        home=tmp_path,
    )

    assert config == client_module.ClientConfig("http://env", "env-token")


def test_generic_config_beats_legacy_config_and_requires_private_mode(tmp_path):
    generic = tmp_path / ".config" / "minimax-h3" / "config.json"
    legacy = tmp_path / ".config" / "committed" / "h3.json"
    generic.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    generic.write_text(json.dumps({"api": "http://new", "token": "new"}))
    legacy.write_text("this stale legacy file must not be parsed")
    if os.name != "nt":
        generic.chmod(0o600)

    config = client_module.load_config(env={}, home=tmp_path)

    assert config == client_module.ClientConfig("http://new", "new")


@pytest.mark.skipif(os.name == "nt", reason="Unix permission check")
def test_rejects_group_readable_token_config(tmp_path):
    config_path = tmp_path / ".config" / "minimax-h3" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"api": "http://new", "token": "secret"}))
    config_path.chmod(0o644)

    with pytest.raises(client_module.ClientError, match="0600"):
        client_module.load_config(env={}, home=tmp_path)


def test_schema_rejects_unknown_protocol_major():
    client, _ = make_client([json_response({"protocol_version": "2.0"})])

    with pytest.raises(client_module.ClientError, match="protocol major"):
        client.schema()


def test_upload_hashes_checks_and_streams_exact_bytes(tmp_path):
    source = tmp_path / "voice.wav"
    source.write_bytes(b"native-h3-audio")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    client, transport = make_client([
        {"status": 404},
        json_response({"blob_id": f"sha256:{digest}"}, status=201),
    ])

    blob_id = client.upload(source, "audio/wav")

    assert blob_id == f"sha256:{digest}"
    assert transport.requests[0][:2] == ("HEAD", f"/v1/blobs/{digest}")
    method, path, headers, body = transport.requests[1]
    assert (method, path) == ("POST", "/v1/blobs")
    assert headers["X-Blob-Sha256"] == blob_id
    assert headers["Content-Length"] == str(source.stat().st_size)
    assert headers["Content-Type"] == "audio/wav"
    assert body == source.read_bytes()


def test_submit_uploads_local_inputs_preserves_order_and_defaults_cache(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    audio = tmp_path / "line.wav"
    for path, value in ((first, b"first"), (second, b"second"), (audio, b"audio")):
        path.write_bytes(value)
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (first, second, audio)]
    responses = []
    for digest in digests:
        responses.extend([{"status": 404}, json_response({"blob_id": f"sha256:{digest}"}, status=201)])
    responses.append(json_response({"handle_id": "handle-1", "attempt_id": "attempt-1", "state": "queued"}, status=202))
    client, transport = make_client(responses)

    result = client.submit({
        "prompt": "<Picture 1>, then <Picture 2>. <Audio 1> is exact dialogue.",
        "local_inputs": {
            "reference_images": [str(first), str(second)],
            "reference_audios": [str(audio)],
        },
    })

    assert result["handle_id"] == "handle-1"
    payload = json.loads(transport.requests[-1][3])
    assert payload["inputs"]["reference_images"] == [f"sha256:{digests[0]}", f"sha256:{digests[1]}"]
    assert payload["inputs"]["reference_audios"] == [f"sha256:{digests[2]}"]
    assert payload["cache_policy"] == "use"
    assert "local_inputs" not in payload


def test_wait_polls_handle_until_terminal_state():
    client, transport = make_client([
        json_response({"handle_id": "h", "attempt_id": "a", "state": "generating"}),
        json_response({"handle_id": "h", "attempt_id": "a", "state": "succeeded", "artifacts": []}),
    ])
    slept = []

    result = client.wait("h", poll_interval=20, sleep=slept.append)

    assert result["state"] == "succeeded"
    assert slept == [20]
    assert [request[1] for request in transport.requests] == [
        "/v1/h3/submissions/h",
        "/v1/h3/submissions/h",
    ]


def test_cancel_uses_handle_cancel_route():
    client, transport = make_client([json_response({"handle_id": "h", "cancelled": True})])

    client.cancel("h")

    assert transport.requests[0][:2] == ("POST", "/v1/h3/submissions/h/cancel")


def test_download_verifies_and_atomically_publishes(tmp_path):
    payload = b"video-with-native-audio"
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    artifact = {
        "artifact_id": "artifact-1",
        "size": len(payload),
        "sha256": digest,
        "etag": f'"{digest.removeprefix("sha256:")}"',
    }
    client, _ = make_client([{
        "status": 200,
        "headers": {
            "Content-Length": str(len(payload)),
            "X-Content-SHA256": digest,
            "ETag": artifact["etag"],
        },
        "body": payload,
    }])
    target = tmp_path / "shot.mp4"

    result = client.download(artifact, target)

    assert result == target
    assert target.read_bytes() == payload
    assert not (tmp_path / "shot.mp4.part").exists()


def test_download_digest_failure_leaves_no_final_file(tmp_path):
    payload = b"corrupt"
    expected = "sha256:" + "0" * 64
    artifact = {"artifact_id": "artifact-1", "size": len(payload), "sha256": expected, "etag": '"' + "0" * 64 + '"'}
    client, _ = make_client([{
        "headers": {"Content-Length": str(len(payload)), "X-Content-SHA256": expected, "ETag": artifact["etag"]},
        "body": payload,
    }])
    target = tmp_path / "shot.mp4"

    with pytest.raises(client_module.ClientError, match="SHA-256"):
        client.download(artifact, target)

    assert not target.exists()
    assert not (tmp_path / "shot.mp4.part").exists()


def test_explicit_refresh_is_preserved_but_never_invented():
    client, transport = make_client([
        json_response({"handle_id": "h", "attempt_id": "a", "state": "queued"}, status=202)
    ])

    client.submit({"prompt": "retry exact creative inputs", "cache_policy": "refresh"})

    payload = json.loads(transport.requests[-1][3])
    assert payload["cache_policy"] == "refresh"
    assert "nonce" not in payload
    assert "cache_key" not in payload


def test_cli_exposes_complete_command_surface_without_token_argument():
    parser = client_module.build_parser()
    help_text = parser.format_help()

    for command in ("doctor", "schema", "upload", "submit", "status", "wait", "cancel", "download"):
        assert command in help_text
    assert "--token" not in help_text


def test_stdlib_transport_end_to_end_over_loopback(tmp_path):
    artifact_bytes = b"native-mp4-and-audio"
    artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()
    state = {"uploaded": None, "submission": None}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *_args):
            pass

        def _json(self, value, status=200):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            if self.headers.get("Authorization") == "Bearer secret":
                return True
            self._json({"error": {"code": "unauthorized", "message": "token required"}}, 401)
            return False

        def do_HEAD(self):
            assert self._authorized()
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            assert self._authorized()
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if self.path == "/v1/blobs":
                state["uploaded"] = body
                self._json({"blob_id": self.headers["X-Blob-Sha256"]}, 201)
            elif self.path == "/v1/h3/submissions":
                state["submission"] = json.loads(body)
                self._json({"handle_id": "h", "attempt_id": "a", "state": "queued"}, 202)
            else:
                self._json({"handle_id": "h", "cancelled": True})

        def do_GET(self):
            if self.path == "/health/live":
                return self._json({"status": "live"})
            assert self._authorized()
            if self.path == "/health/ready":
                return self._json({"status": "ready"})
            if self.path == "/v1/h3/schema":
                return self._json({"protocol_version": "1.0", "compatible": True})
            if self.path == "/v1/h3/submissions/h":
                return self._json({
                    "handle_id": "h",
                    "attempt_id": "a",
                    "state": "succeeded",
                    "artifacts": [{
                        "artifact_id": "artifact-1",
                        "kind": "video",
                        "size": len(artifact_bytes),
                        "sha256": "sha256:" + artifact_digest,
                        "etag": f'"{artifact_digest}"',
                    }],
                })
            if self.path == "/v1/artifacts/artifact-1":
                self.send_response(200)
                self.send_header("Content-Length", str(len(artifact_bytes)))
                self.send_header("X-Content-SHA256", "sha256:" + artifact_digest)
                self.send_header("ETag", f'"{artifact_digest}"')
                self.end_headers()
                self.wfile.write(artifact_bytes)
                return
            self._json({"error": {"code": "not_found", "message": "not found"}}, 404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source = tmp_path / "voice.wav"
        source.write_bytes(b"dialogue")
        client = client_module.H3Client(
            client_module.ClientConfig(f"http://127.0.0.1:{server.server_port}", "secret")
        )
        assert client.doctor()["schema"]["compatible"] is True
        blob_id = client.upload(source)
        submitted = client.submit({"prompt": "<Audio 1>", "inputs": {"reference_audios": [blob_id]}})
        final = client.wait(submitted["handle_id"])
        target = client.download(final["artifacts"][0], tmp_path / "line.mp4")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert state["uploaded"] == b"dialogue"
    assert state["submission"]["cache_policy"] == "use"
    assert target.read_bytes() == artifact_bytes
