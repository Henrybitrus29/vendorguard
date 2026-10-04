import io

DOC = b"Master Services Agreement. Tax ID: 12-3456789. Vendor shall indemnify the client. SLA 99.9%."


def upload(c, title="Acme MSA", content=DOC, name="msa.txt"):
    return c.post("/submissions", data={"title": title}, files={"file": (name, io.BytesIO(content), "text/plain")})


def test_csrf_header_required(client):
    r = client.post("/auth/login", json={"email": "a@b.co", "password": "x"}, headers={"X-Requested-With": ""})
    assert r.status_code == 403


def test_login_errors_are_generic(client, make_vendor):
    make_vendor("real@example.com")
    c = make_client_plain()
    wrong_pw = c.post("/auth/login", json={"email": "real@example.com", "password": "nope-nope-nope"})
    no_user = c.post("/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def make_client_plain():
    from tests.conftest import make_client

    return make_client()


def test_register_cannot_choose_admin_role(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "a-long-password-1", "role": "admin"})
    assert r.status_code == 201
    assert r.json()["role"] == "vendor"


def test_upload_is_processed_and_vendor_view_hides_internals(make_vendor):
    v = make_vendor("v1@example.com")
    r = upload(v)
    assert r.status_code == 201
    listing = v.get("/submissions").json()
    assert listing[0]["status"] == "Approved" and listing[0]["stage"] == "decided"
    for secret in ("flags", "checks", "ai_confidence", "extracted_data", "ai_decision"):
        assert secret not in listing[0]


def test_vendor_cannot_read_another_vendors_submission(make_vendor):
    a, b = make_vendor("a@example.com"), make_vendor("b@example.com")
    sid = upload(a).json()["id"]
    assert b.get(f"/submissions/{sid}").status_code == 404
    assert b.get(f"/submissions/{sid}/file").status_code == 404
    assert a.get(f"/submissions/{sid}/file").status_code == 200


def test_vendor_cannot_use_admin_endpoints(make_vendor):
    v = make_vendor("v2@example.com")
    sid = upload(v).json()["id"]
    assert v.get("/admin/metrics").status_code == 403
    assert v.get("/admin/audit-log.csv").status_code == 403
    r = v.patch(f"/submissions/{sid}/override", json={"new_status": "Approved", "reason": "I would like this please"})
    assert r.status_code == 403


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/submissions").status_code == 401
    assert client.get("/admin/metrics").status_code == 401


def test_fake_pdf_and_binary_files_are_rejected(make_vendor):
    v = make_vendor("v3@example.com")
    assert upload(v, content=b"MZ\x90\x00\x03\x00\x00\x00", name="evil.pdf").status_code == 415
    assert upload(v, content=b"\xff\xfe\x00\x01binary", name="x.txt").status_code == 415


def test_admin_override_needs_reason_and_is_logged(make_vendor, admin_client):
    v = make_vendor("v4@example.com")
    sid = upload(v).json()["id"]
    assert admin_client.patch(f"/submissions/{sid}/override", json={"new_status": "Rejected", "reason": "short"}).status_code == 422
    assert admin_client.patch(f"/submissions/{sid}/override", json={"new_status": "Hacked", "reason": "a valid long reason"}).status_code == 422
    ok = admin_client.patch(f"/submissions/{sid}/override", json={"new_status": "Rejected", "reason": "Vendor is on our blocklist"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "Rejected" and body["overrides"][0]["admin_email"] == "boss@example.com"
    again = admin_client.patch(f"/submissions/{sid}/override", json={"new_status": "Rejected", "reason": "Vendor is on our blocklist"})
    assert again.status_code == 409


def test_metrics_reflect_overrides(make_vendor, admin_client):
    v = make_vendor("v5@example.com")
    s1, s2 = upload(v).json()["id"], upload(v, title="Second doc").json()["id"]
    admin_client.patch(f"/submissions/{s1}/override", json={"new_status": "Rejected", "reason": "Blocklisted supplier here"})
    m = admin_client.get("/admin/metrics").json()
    assert m["total"] == 2 and m["overrides_total"] == 1
    assert m["ai_agreement_pct"] == 50.0 and m["auto_approved_pct"] == 100.0
    assert s2


def test_csv_export_neutralises_formula_injection(make_vendor, admin_client):
    v = make_vendor("v6@example.com")
    sid = upload(v).json()["id"]
    admin_client.patch(f"/submissions/{sid}/override", json={"new_status": "Rejected", "reason": "=HYPERLINK(\"http://evil\",\"x\")"})
    csv_text = admin_client.get("/admin/audit-log.csv").text
    assert "'=HYPERLINK" in csv_text
    assert ",=HYPERLINK" not in csv_text


def png_bytes():
    import io as _io
    from PIL import Image

    buf = _io.BytesIO()
    Image.new("L", (200, 100), 255).save(buf, "PNG")
    return buf.getvalue()


def test_image_upload_is_accepted_and_typed_by_content(make_vendor, admin_client):
    v = make_vendor("img@example.com")
    r = upload(v, content=png_bytes(), name="scan.png")
    assert r.status_code == 201
    detail = admin_client.get(f"/submissions/{r.json()['id']}").json()
    assert detail["content_type"] == "image/png"
    assert detail["extracted_data"]["extraction"]["method"] in ("ocr", "none")  # none if tesseract is absent
    assert v.get(f"/submissions/{r.json()['id']}/file").headers["content-type"] == "image/png"


def test_unsupported_image_types_are_rejected(make_vendor):
    v = make_vendor("gif@example.com")
    assert upload(v, content=b"GIF89a" + b"\x00" * 50, name="x.gif").status_code == 415
    assert upload(v, content=b"<svg onload=alert(1)></svg>\x00", name="x.svg").status_code == 415
