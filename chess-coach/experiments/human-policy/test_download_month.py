import hashlib
import io
import json
from types import SimpleNamespace

import pytest
import download_month as dm


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {"Content-Length": str(len(body))}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    body = b"complete-compressed-month-fixture"
    meta = dict(month="2026-09", name="month.zst", url="https://example.invalid/month.zst",
                bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), etag='"v1"')
    monkeypatch.setattr(dm, "remote_metadata", lambda month: meta)
    monkeypatch.setattr(dm.shutil, "disk_usage", lambda path: SimpleNamespace(free=100*dm.GIB))
    return tmp_path, body, meta


@pytest.mark.parametrize("offset", [0, 7])
def test_complete_and_resumed_download_verify_same_hash(setup, monkeypatch, offset):
    folder, body, meta = setup
    if offset:
        (folder / "month.zst.part").write_bytes(body[:offset])
        dm.write_json(folder / "2026-09.manifest.json", meta)
    def open_request(request, **kwargs):
        assert request.get_header("Range") == (f"bytes={offset}-" if offset else None)
        headers = {"Content-Length": str(len(body)-offset)}
        if offset:
            headers["Content-Range"] = f"bytes {offset}-{len(body)-1}/{len(body)}"
        return Response(body[offset:], 206 if offset else 200, headers)
    monkeypatch.setattr(dm.urllib.request, "urlopen", open_request)
    dm.download("2026-09", folder, folder)
    assert (folder / "month.zst").read_bytes() == body
    assert not (folder / "month.zst.part").exists()
    assert json.loads((folder / "2026-09.status.json").read_text())["state"] == "complete"
    # Re-running verifies the existing file without downloading it again.
    monkeypatch.setattr(dm.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected download"))
    dm.download("2026-09", folder, folder)


def test_rejected_range_keeps_partial_intact(setup, monkeypatch):
    folder, body, meta = setup
    part = folder / "month.zst.part"
    part.write_bytes(body[:7])
    dm.write_json(folder / "2026-09.manifest.json", meta)
    monkeypatch.setattr(dm.urllib.request, "urlopen", lambda *a, **kw: Response(body))
    with pytest.raises(ValueError, match="ripresa esatta"):
        dm.download("2026-09", folder, folder)
    assert part.read_bytes() == body[:7]


def test_bad_checksum_never_promotes_archive(setup, monkeypatch):
    folder, body, meta = setup
    monkeypatch.setattr(dm.urllib.request, "urlopen", lambda *a, **kw: Response(b"x"*len(body)))
    with pytest.raises(ValueError, match="Checksum"):
        dm.download("2026-09", folder, folder)
    assert not (folder / "month.zst").exists()
    assert json.loads((folder / "2026-09.status.json").read_text())["state"] == "failed"


def test_physical_host_space_blocks_download(setup, monkeypatch):
    folder, body, meta = setup
    monkeypatch.setattr(dm.shutil, "disk_usage", lambda path: SimpleNamespace(free=100*dm.GIB if path == folder else dm.GIB))
    monkeypatch.setattr(dm.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected download"))
    with pytest.raises(RuntimeError, match="Spazio insufficiente"):
        dm.download("2026-09", folder, "host-disk")


def test_interruption_retries_from_last_written_byte(setup, monkeypatch):
    folder, body, meta = setup
    monkeypatch.setattr(dm, "CHUNK", 4)
    monkeypatch.setattr(dm.time, "sleep", lambda value: None)
    class Interrupted(Response):
        def read(self, count):
            if self.tell():
                raise ConnectionResetError("fixture")
            return super().read(count)
    attempts = []
    def open_request(request, **kwargs):
        attempts.append(request.get_header("Range"))
        if len(attempts) == 1:
            return Interrupted(body)
        return Response(body[4:], 206, {"Content-Length": str(len(body)-4),
                                        "Content-Range": f"bytes 4-{len(body)-1}/{len(body)}"})
    monkeypatch.setattr(dm.urllib.request, "urlopen", open_request)
    dm.download("2026-09", folder, folder)
    assert attempts == [None, "bytes=4-"]
    assert (folder / "month.zst").read_bytes() == body


def test_manifest_change_blocks_resume(setup):
    folder, body, meta = setup
    dm.write_json(folder / "2026-09.manifest.json", {**meta, "etag": "old"})
    with pytest.raises(ValueError, match="remoto cambiato"):
        dm.download("2026-09", folder, folder)


def test_remote_metadata_checks_official_checksum(monkeypatch):
    digest = "a" * 64
    def open_request(request, **kwargs):
        if isinstance(request, str):
            return Response(f"{digest}  lichess_db_standard_rated_2026-09.pgn.zst\n".encode())
        assert request.get_method() == "HEAD"
        return Response(b"", headers={"Content-Length": "123", "ETag": "tag"})
    monkeypatch.setattr(dm.urllib.request, "urlopen", open_request)
    result = dm.remote_metadata("2026-09")
    assert result["bytes"] == 123 and result["sha256"] == digest
    with pytest.raises(ValueError, match="Mese non valido"):
        dm.remote_metadata("../bad")
