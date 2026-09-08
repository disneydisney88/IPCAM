from __future__ import annotations


def test_credential_book_auto_applies_on_camera_creation(client):
    content = "10.9.9.9, svc, Book-Pass-1, /streaming, sub\n"
    imported = client.post("/api/credentials/book/import?replace=true", json={"content": content})
    assert imported.status_code == 200, imported.text
    assert imported.json()["total"] == 1

    created = client.post("/api/cameras", json={"name": "Book Cam", "ip": "10.9.9.9"})
    assert created.status_code == 201, created.text
    camera_id = created.json()["id"]

    status = client.get(f"/api/cameras/{camera_id}/credentials").json()
    assert status["configured"] is True
    assert "sub" in status["stream_kinds"]

    summary = client.get("/api/credentials/book").json()
    assert summary["total"] == 1
    assert summary["entries"][0]["camera_id"] == camera_id
    assert "password" not in summary["entries"][0]

    applied = client.post("/api/credentials/book/apply").json()
    assert applied["matched"] >= 1

    assert client.delete("/api/credentials/book").status_code == 204
    assert client.get("/api/credentials/book").json()["total"] == 0
    client.delete(f"/api/cameras/{camera_id}")


def test_credential_book_rejects_bad_rows_and_replaces(client):
    content = "10.9.9.9, svc, Book-Pass-1\nbad-row\n"
    imported = client.post("/api/credentials/book/import?replace=true", json={"content": content})
    assert imported.json()["total"] == 1
    assert len(imported.json()["errors"]) == 1

    again = client.post("/api/credentials/book/import?replace=true", json={"content": "10.9.9.10, svc2, Book-Pass-2\n"})
    assert again.json()["total"] == 1

    appended = client.post("/api/credentials/book/import?replace=false", json={"content": "10.9.9.9, svc, Book-Pass-1\n"})
    assert appended.json()["total"] == 2
    client.delete("/api/credentials/book")
