"""Connection tests for Phase 3A."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.connections import models as cm
from app.modules.forum import models as fm
from app.modules.identity import models as m
from app.modules.identity import security as sec
from tests.conftest import auth_headers, register_payload


def _register(client, university, class_id, **overrides):
    uni_id = university.id if hasattr(university, "id") else university
    resp = client.post("/api/v1/auth/register", json=register_payload(uni_id, class_id, **overrides))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["token"], body["user"]["id"]


@pytest.fixture()
def alice(client, university, class_id):
    token, uid = _register(client, university, class_id, email="alice@test.edu", student_no="TEST-A01")
    return token, uid


@pytest.fixture()
def bob(client, university, class_id):
    token, uid = _register(client, university, class_id, email="bob@test.edu", student_no="TEST-B01")
    return token, uid


@pytest.fixture()
def carol(client, university, class_id):
    token, uid = _register(client, university, class_id, email="carol@test.edu", student_no="TEST-C01")
    return token, uid


@pytest.fixture()
def other_university(db_session):
    uni = m.University(
        name="Other University",
        code="OTHER2-U",
        email_domain="other2.edu",
        enrollment_code_hash=sec.hash_password("OTHER123"),
    )
    db_session.add(uni)
    db_session.flush()
    dept = m.Department(university_id=uni.id, name="Math", code="MATH")
    db_session.add(dept)
    db_session.flush()
    prog = m.Program(department_id=dept.id, name="BSc Math", code="MATH-BSC", degree_level="BSc")
    db_session.add(prog)
    db_session.flush()
    batch = m.Batch(program_id=prog.id, name="2024", start_year=2024)
    db_session.add(batch)
    db_session.flush()
    cls = m.Class(batch_id=batch.id, name="MATH-2024-A", code="A")
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(uni)
    return uni


# ---- Request creation ----

def test_request_creation_success(client, alice, bob, db_session):
    a_token, a_id = alice
    b_token, b_id = bob
    resp = client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["requester_id"] == a_id
    assert body["recipient_id"] == b_id
    # notification created
    notif = db_session.scalar(select(fm.Notification).where(fm.Notification.user_id == uuid.UUID(b_id), fm.Notification.type == "CONNECTION_REQUEST"))
    assert notif is not None
    assert "connection request" in notif.message.lower()


def test_cannot_send_to_self(client, alice):
    a_token, a_id = alice
    resp = client.post(f"/api/v1/connections/{a_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 409


def test_cannot_send_to_nonexistent(client, alice):
    a_token, _ = alice
    resp = client.post(f"/api/v1/connections/{uuid.uuid4()}/request", headers=auth_headers(a_token))
    assert resp.status_code == 404


def test_cannot_send_if_unverified(client, university, class_id):
    # unverified student (wrong code)
    token_unverified, uid_unverified = _register(
        client, university, class_id, email="pending@test.edu", student_no="PEND-001", enrollment_code="WRONG"
    )
    # another verified student
    token_verified, uid_verified = _register(
        client, university, class_id, email="verified2@test.edu", student_no="VER-001"
    )
    # unverified cannot send
    resp = client.post(f"/api/v1/connections/{uid_verified}/request", headers=auth_headers(token_unverified))
    assert resp.status_code == 403
    # cannot send to unverified
    resp2 = client.post(f"/api/v1/connections/{uid_unverified}/request", headers=auth_headers(token_verified))
    assert resp2.status_code == 403


def test_cannot_send_across_universities(client, alice, other_university, db_session):
    a_token, _ = alice
    other_cls = db_session.scalar(select(m.Class).where(m.Class.name == "MATH-2024-A"))
    o_token, o_id = _register(
        client, other_university, str(other_cls.id), email="other@other2.edu", student_no="OUT-001", enrollment_code="OTHER123"
    )
    resp = client.post(f"/api/v1/connections/{o_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 403
    # other trying to connect to alice also forbidden
    _, a_id = alice
    resp3 = client.post(f"/api/v1/connections/{a_id}/request", headers=auth_headers(o_token))
    assert resp3.status_code == 403


def test_duplicate_request_rejected(client, alice, bob):
    a_token, _ = alice
    _, b_id = bob
    assert client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token)).status_code == 201
    dup = client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert dup.status_code == 409
    # reverse duplicate also rejected
    b_token, _ = bob
    _, a_id = alice
    rev = client.post(f"/api/v1/connections/{a_id}/request", headers=auth_headers(b_token))
    assert rev.status_code == 409


def test_request_to_already_connected_rejected(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token)).status_code == 200
    # now try again
    resp = client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 409
    resp2 = client.post(f"/api/v1/connections/{a_id}/request", headers=auth_headers(b_token))
    assert resp2.status_code == 409


# ---- Accept ----

def test_accept_success(client, alice, bob, db_session):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ACCEPTED"
    # notification to requester
    notif = db_session.scalar(select(fm.Notification).where(fm.Notification.user_id == uuid.UUID(a_id), fm.Notification.type == "CONNECTION_ACCEPTED"))
    assert notif is not None
    assert "accepted" in notif.message.lower()
    # persisted
    conn = db_session.scalar(select(cm.Connection).where(cm.Connection.requester_id == uuid.UUID(a_id), cm.Connection.recipient_id == uuid.UUID(b_id)))
    assert conn.status == cm.ConnectionStatus.ACCEPTED


def test_requester_cannot_accept_own(client, alice, bob):
    a_token, a_id = alice
    _, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.post(f"/api/v1/connections/{b_id}/accept", headers=auth_headers(a_token))
    assert resp.status_code == 404


def test_unrelated_cannot_accept(client, alice, bob, carol):
    a_token, a_id = alice
    _, b_id = bob
    c_token, _ = carol
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    # carol tries to accept
    resp = client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(c_token))
    assert resp.status_code == 404


# ---- Reject ----

def test_reject_success(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.post(f"/api/v1/connections/{a_id}/reject", headers=auth_headers(b_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "REJECTED"


def test_unrelated_cannot_reject(client, alice, bob, carol):
    a_token, a_id = alice
    _, b_id = bob
    c_token, _ = carol
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.post(f"/api/v1/connections/{a_id}/reject", headers=auth_headers(c_token))
    assert resp.status_code == 404


def test_reject_allows_new_request(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/reject", headers=auth_headers(b_token))
    # alice can send again after rejection
    resp = client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 201


# ---- Cancel ----

def test_cancel_success(client, alice, bob):
    a_token, _ = alice
    _, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.delete(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 204
    # verify gone
    b_token, _ = bob
    a_id = alice[1]
    status = client.get(f"/api/v1/connections/{b_id}/status", headers=auth_headers(a_token)).json()
    assert status["status"] == "NONE"
    status2 = client.get(f"/api/v1/connections/{a_id}/status", headers=auth_headers(b_token)).json()
    assert status2["status"] == "NONE"


def test_recipient_cannot_cancel(client, alice, bob):
    a_token, _ = alice
    b_token, _ = bob
    _, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.delete(f"/api/v1/connections/{b_id}/request", headers=auth_headers(b_token))
    assert resp.status_code == 404


def test_unrelated_cannot_cancel(client, alice, bob, carol):
    a_token, _ = alice
    c_token, _ = carol
    _, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    resp = client.delete(f"/api/v1/connections/{b_id}/request", headers=auth_headers(c_token))
    assert resp.status_code == 404


# ---- Remove ----

def test_remove_by_either(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    # bob removes
    resp = client.delete(f"/api/v1/connections/{a_id}", headers=auth_headers(b_token))
    assert resp.status_code == 204
    # verify removed
    assert client.get(f"/api/v1/connections", headers=auth_headers(a_token)).json() == []
    assert client.get(f"/api/v1/connections", headers=auth_headers(b_token)).json() == []


def test_remove_by_requester_also_works(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    resp = client.delete(f"/api/v1/connections/{b_id}", headers=auth_headers(a_token))
    assert resp.status_code == 204


def test_unrelated_cannot_remove(client, alice, bob, carol):
    a_token, a_id = alice
    b_token, b_id = bob
    c_token, _ = carol
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    resp = client.delete(f"/api/v1/connections/{b_id}", headers=auth_headers(c_token))
    assert resp.status_code == 404


def test_removed_can_send_new_request(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    client.delete(f"/api/v1/connections/{b_id}", headers=auth_headers(a_token))
    resp = client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert resp.status_code == 201


# ---- Status ----

def test_status_variants(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    # none
    assert client.get(f"/api/v1/connections/{b_id}/status", headers=auth_headers(a_token)).json()["status"] == "NONE"
    # pending outgoing from alice view
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    assert client.get(f"/api/v1/connections/{b_id}/status", headers=auth_headers(a_token)).json()["status"] == "PENDING_OUTGOING"
    assert client.get(f"/api/v1/connections/{a_id}/status", headers=auth_headers(b_token)).json()["status"] == "PENDING_INCOMING"
    # after accept
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    assert client.get(f"/api/v1/connections/{b_id}/status", headers=auth_headers(a_token)).json()["status"] == "CONNECTED"
    assert client.get(f"/api/v1/connections/{a_id}/status", headers=auth_headers(b_token)).json()["status"] == "CONNECTED"


def test_status_rejected(client, alice, bob):
    a_token, a_id = alice
    b_token, b_id = bob
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/reject", headers=auth_headers(b_token))
    st = client.get(f"/api/v1/connections/{b_id}/status", headers=auth_headers(a_token)).json()["status"]
    assert st == "REJECTED"


# ---- Lists ----

def test_lists(client, alice, bob, carol):
    a_token, a_id = alice
    b_token, b_id = bob
    c_token, c_id = carol
    # alice -> bob pending, alice -> carol pending
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{c_id}/request", headers=auth_headers(a_token))
    # outgoing for alice =2
    assert len(client.get("/api/v1/connections/requests/outgoing", headers=auth_headers(a_token)).json()) == 2
    # incoming for bob =1
    assert len(client.get("/api/v1/connections/requests/incoming", headers=auth_headers(b_token)).json()) == 1
    # accept bob
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    # connections for alice =1 (bob)
    conns = client.get("/api/v1/connections", headers=auth_headers(a_token)).json()
    assert len(conns) == 1
    assert conns[0]["user_id"] == b_id
    # carol still pending
    assert len(client.get("/api/v1/connections/requests/outgoing", headers=auth_headers(a_token)).json()) == 1


# ---- Mutuals ----

def test_mutuals_correct(client, alice, bob, carol):
    a_token, a_id = alice
    b_token, b_id = bob
    c_token, c_id = carol
    # alice-bob accepted, alice-carol accepted, bob-carol accepted? then alice<->bob mutual is carol?
    # Setup: alice<->bob, alice<->carol, bob<->cara??? Let's create triangle with carol as mutual
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    client.post(f"/api/v1/connections/{c_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(c_token))
    # Need bob-carol connection
    # create extra user dave to be mutual? Simpler: bob connects to carol directly
    # alice already connected to carol, so for bob-carol to be mutual via alice: both bob and carol connected to alice
    # So mutuals between bob and carol should be alice
    client.post(f"/api/v1/connections/{c_id}/request", headers=auth_headers(b_token))
    client.post(f"/api/v1/connections/{b_id}/accept", headers=auth_headers(c_token))
    # now alice's connections: bob, carol ; bob's: alice, carol ; carol's: alice, bob
    # mutual bob<->carol = alice
    resp = client.get(f"/api/v1/connections/{c_id}/mutuals", headers=auth_headers(b_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert body["users"][0]["user_id"] == a_id
    # mutual alice<->bob = carol
    resp2 = client.get(f"/api/v1/connections/{b_id}/mutuals", headers=auth_headers(a_token))
    assert resp2.json()["count"] == 1
    assert resp2.json()["users"][0]["user_id"] == c_id
    pass


def test_mutuals_no_unrelated(client, alice, bob, carol):
    a_token, a_id = alice
    b_token, b_id = bob
    c_token, c_id = carol
    # only alice-bob connected
    client.post(f"/api/v1/connections/{b_id}/request", headers=auth_headers(a_token))
    client.post(f"/api/v1/connections/{a_id}/accept", headers=auth_headers(b_token))
    # alice<->carol no mutuals
    resp = client.get(f"/api/v1/connections/{c_id}/mutuals", headers=auth_headers(a_token))
    assert resp.json()["count"] == 0
    assert resp.json()["users"] == []


def test_mutuals_cross_university_forbidden(client, alice, other_university, db_session):
    a_token, a_id = alice
    other_cls = db_session.scalar(select(m.Class).where(m.Class.name == "MATH-2024-A"))
    o_token, o_id = _register(client, other_university, str(other_cls.id), email="other3@other2.edu", student_no="OUT-003", enrollment_code="OTHER123")
    resp = client.get(f"/api/v1/connections/{o_id}/mutuals", headers=auth_headers(a_token))
    assert resp.status_code == 403


# ---- Auth required ----

def test_auth_required(client, alice):
    _, b_id = alice
    # reuse alice token but without auth should 401
    import uuid as _uuid
    assert client.post(f"/api/v1/connections/{_uuid.uuid4()}/request").status_code == 401
    assert client.get("/api/v1/connections").status_code == 401
    assert client.get(f"/api/v1/connections/{b_id}/status").status_code == 401
