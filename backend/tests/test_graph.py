"""Graph tests for Phase 3B-A."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.connections import models as cm
from app.modules.forum import models as fm
from app.modules.identity import models as m
from app.modules.identity import security as sec
from app.modules.profile import models as pm
from tests.conftest import auth_headers, register_payload


def _register(client, university, class_id, **overrides):
    uni_id = university.id if hasattr(university, "id") else university
    resp = client.post("/api/v1/auth/register", json=register_payload(uni_id, class_id, **overrides))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["token"], body["user"]["id"]


@pytest.fixture()
def alice(client, university, class_id):
    token, uid = _register(client, university, class_id, email="alice@test.edu", student_no="TEST-A01", display_name="Alice")
    return token, uid


@pytest.fixture()
def bob(client, university, class_id):
    token, uid = _register(client, university, class_id, email="bob@test.edu", student_no="TEST-B01", display_name="Bob")
    return token, uid


@pytest.fixture()
def carol(client, university, class_id):
    token, uid = _register(client, university, class_id, email="carol@test.edu", student_no="TEST-C01", display_name="Carol")
    return token, uid


@pytest.fixture()
def other_university(db_session):
    uni = m.University(
        name="Other University",
        code="OTHER-G-U",
        email_domain="othergraph.edu",
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


# ---- Helpers ----

def _add_skill(db_session, user_id, name):
    skill = db_session.scalar(select(pm.Skill).where(pm.Skill.name == name))
    if skill is None:
        skill = pm.Skill(name=name)
        db_session.add(skill)
        db_session.flush()
    if db_session.scalar(select(pm.ProfileSkill).where(pm.ProfileSkill.user_id == uuid.UUID(user_id) if isinstance(user_id, str) else user_id, pm.ProfileSkill.skill_id == skill.id)) is None:
        db_session.add(pm.ProfileSkill(user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id, skill_id=skill.id, source="manual"))
    db_session.flush()


def _add_interest(db_session, user_id, name, kind="INTEREST"):
    interest = db_session.scalar(select(pm.Interest).where(pm.Interest.name == name))
    if interest is None:
        interest = pm.Interest(name=name, kind=kind)
        db_session.add(interest)
        db_session.flush()
    if db_session.scalar(select(pm.ProfileInterest).where(pm.ProfileInterest.user_id == uuid.UUID(user_id) if isinstance(user_id, str) else user_id, pm.ProfileInterest.interest_id == interest.id)) is None:
        db_session.add(pm.ProfileInterest(user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id, interest_id=interest.id, source="manual"))
    db_session.flush()


def _create_forum(db_session, class_id, name, status, creator_id=None):
    forum = fm.Forum(class_id=uuid.UUID(class_id) if isinstance(class_id, str) else class_id, name=name, description="desc", status=status, created_by=uuid.UUID(creator_id) if isinstance(creator_id, str) else creator_id)
    db_session.add(forum)
    db_session.flush()
    return forum


def _join_forum(db_session, forum_id, user_id):
    fid = uuid.UUID(forum_id) if isinstance(forum_id, str) else forum_id
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    if db_session.scalar(select(fm.ForumMembership).where(fm.ForumMembership.forum_id == fid, fm.ForumMembership.user_id == uid)) is None:
        db_session.add(fm.ForumMembership(forum_id=fid, user_id=uid))
        db_session.flush()


def _add_connection(db_session, requester_id, recipient_id, status):
    req = uuid.UUID(requester_id) if isinstance(requester_id, str) else requester_id
    rec = uuid.UUID(recipient_id) if isinstance(recipient_id, str) else recipient_id
    conn = cm.Connection(requester_id=req, recipient_id=rec, status=status)
    db_session.add(conn)
    db_session.flush()
    return conn


# ---- Authentication ----

def test_graph_unauthenticated_denied(client):
    resp = client.get("/api/v1/graph/me")
    assert resp.status_code == 401


def test_graph_verified_student_succeeds(client, alice):
    token, uid = alice
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["root_id"] == uid
    assert len(body["nodes"]) >= 1
    assert len(body["edges"]) >= 0


def test_graph_unverified_denied(client, university, class_id):
    token, uid = _register(client, university, class_id, email="pending@test.edu", student_no="PEND-001", enrollment_code="WRONG", display_name="Pending")
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    assert resp.status_code == 403


# ---- University hierarchy ----

def test_graph_university_hierarchy(client, alice, university, class_id, db_session):
    token, uid = alice
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    nodes = {n["type"]: n for n in body["nodes"]}
    # Check existence of each academic type
    types = {n["type"] for n in body["nodes"]}
    assert "UNIVERSITY" in types
    assert "DEPARTMENT" in types
    assert "PROGRAM" in types
    assert "BATCH" in types
    assert "CLASS" in types
    assert "STUDENT" in types
    # Labels should match seed structure
    uni_node = next(n for n in body["nodes"] if n["type"] == "UNIVERSITY")
    assert uni_node["label"] == "Test University"
    dept_node = next(n for n in body["nodes"] if n["type"] == "DEPARTMENT")
    assert dept_node["label"] == "CS"
    prog_node = next(n for n in body["nodes"] if n["type"] == "PROGRAM")
    assert prog_node["label"] == "BSc CS"
    batch_node = next(n for n in body["nodes"] if n["type"] == "BATCH")
    assert batch_node["label"] == "2024"
    class_node = next(n for n in body["nodes"] if n["type"] == "CLASS")
    assert class_node["label"] == "CS-2024-A"
    # Edges should exist and reference valid nodes
    node_ids = {n["id"] for n in body["nodes"]}
    for e in body["edges"]:
        assert e["source"] in node_ids
        assert e["target"] in node_ids
        assert e["type"] in {"BELONGS_TO", "ENROLLED_IN", "IN_PROGRAM", "IN_BATCH", "IN_CLASS", "PARTICIPATES_IN", "HAS_SKILL", "HAS_INTEREST", "CONNECTED_TO", "MEMBER_OF"}
    # Specific hierarchy edges
    # Department -> University
    dept_id = dept_node["id"]
    uni_id = uni_node["id"]
    assert any(e["type"] == "BELONGS_TO" and e["source"] == dept_id and e["target"] == uni_id for e in body["edges"])
    # Program -> Department
    prog_id = prog_node["id"]
    assert any(e["type"] == "IN_PROGRAM" and e["source"] == prog_id and e["target"] == dept_id for e in body["edges"])
    # Batch -> Program
    batch_id = batch_node["id"]
    assert any(e["type"] == "IN_BATCH" and e["source"] == batch_id and e["target"] == prog_id for e in body["edges"])
    # Class -> Batch
    class_id_node = class_node["id"]
    assert any(e["type"] == "IN_CLASS" and e["source"] == class_id_node and e["target"] == batch_id for e in body["edges"])
    # Student -> Class
    assert any(e["type"] == "IN_CLASS" and e["source"] == body["root_id"] and e["target"] == class_id_node for e in body["edges"])
    # Student -> University
    assert any(e["type"] == "ENROLLED_IN" and e["source"] == body["root_id"] and e["target"] == uni_id for e in body["edges"])


# ---- Forums ----

def test_graph_forums_joined_approved_appears(client, alice, university, class_id, db_session):
    token, uid = alice
    # create approved forum and join
    forum = _create_forum(db_session, class_id, "Graph Forum A", fm.ForumStatus.APPROVED, uid)
    _join_forum(db_session, forum.id, uid)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    body = resp.json()
    forum_nodes = [n for n in body["nodes"] if n["type"] == "FORUM"]
    assert any(n["label"] == "Graph Forum A" for n in forum_nodes)
    # edge from root to forum
    assert any(e["type"] == "PARTICIPATES_IN" and e["source"] == uid and e["target"] == str(forum.id) for e in body["edges"])


def test_graph_unjoined_approved_not_appears(client, alice, university, class_id, db_session):
    token, uid = alice
    forum = _create_forum(db_session, class_id, "Unjoined Forum", fm.ForumStatus.APPROVED, uid)
    # do not join
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    body = resp.json()
    assert not any(n["id"] == str(forum.id) for n in body["nodes"])


def test_graph_pending_forum_not_appears(client, alice, university, class_id, db_session):
    token, uid = alice
    forum = _create_forum(db_session, class_id, "Pending Forum", fm.ForumStatus.PENDING, uid)
    _join_forum(db_session, forum.id, uid)  # even if joined, status pending should not appear (only approved)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    body = resp.json()
    assert not any(n["id"] == str(forum.id) for n in body["nodes"])


def test_graph_rejected_forum_not_appears(client, alice, university, class_id, db_session):
    token, uid = alice
    forum = _create_forum(db_session, class_id, "Rejected Forum", fm.ForumStatus.REJECTED, uid)
    _join_forum(db_session, forum.id, uid)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    body = resp.json()
    assert not any(n["id"] == str(forum.id) for n in body["nodes"])


# ---- Skills / Interests ----

def test_graph_skills_correct(client, alice, db_session):
    token, uid = alice
    _add_skill(db_session, uid, "python")
    _add_skill(db_session, uid, "fastapi")
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    body = resp.json()
    skill_nodes = [n for n in body["nodes"] if n["type"] == "SKILL"]
    labels = {n["label"] for n in skill_nodes}
    assert "python" in labels
    assert "fastapi" in labels
    assert "unrelatedskill" not in labels
    # edge
    skill_id = next(n["id"] for n in skill_nodes if n["label"] == "python")
    assert any(e["type"] == "HAS_SKILL" and e["source"] == uid and e["target"] == skill_id for e in body["edges"])


def test_graph_unrelated_skills_not_appear(client, alice, bob, db_session):
    token_a, uid_a = alice
    token_b, uid_b = bob
    _add_skill(db_session, uid_b, "secret-skill-bob")
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    assert not any(n["label"] == "secret-skill-bob" for n in body["nodes"])


def test_graph_interests_correct(client, alice, db_session):
    token, uid = alice
    _add_interest(db_session, uid, "robotics", "INTEREST")
    _add_interest(db_session, uid, "chess", "HOBBY")
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token))
    body = resp.json()
    interest_nodes = [n for n in body["nodes"] if n["type"] == "INTEREST"]
    labels = {n["label"] for n in interest_nodes}
    assert "robotics" in labels
    assert "chess" in labels
    # edge
    iid = next(n["id"] for n in interest_nodes if n["label"] == "robotics")
    assert any(e["type"] == "HAS_INTEREST" and e["source"] == uid and e["target"] == iid for e in body["edges"])


def test_graph_unrelated_interests_not_appear(client, alice, bob, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _add_interest(db_session, uid_b, "bob-unique-interest")
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    assert not any(n["label"] == "bob-unique-interest" for n in body["nodes"])


# ---- Connections ----

def test_graph_accepted_connection_appears(client, alice, bob, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _add_connection(db_session, uid_a, uid_b, cm.ConnectionStatus.ACCEPTED)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    # bob should appear as STUDENT node (in addition to root)
    student_nodes = [n for n in body["nodes"] if n["type"] == "STUDENT"]
    assert any(n["id"] == uid_b for n in student_nodes)
    bob_node = next(n for n in student_nodes if n["id"] == uid_b)
    # privacy: no email, no student_no
    assert "email" not in str(bob_node["metadata"]).lower()
    assert "student_no" not in str(bob_node["metadata"]).lower()
    # edge
    assert any(e["type"] == "CONNECTED_TO" and e["source"] == uid_a and e["target"] == uid_b for e in body["edges"])


def test_graph_pending_not_appears(client, alice, bob, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _add_connection(db_session, uid_a, uid_b, cm.ConnectionStatus.PENDING)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    assert not any(n["id"] == uid_b and n["type"] == "STUDENT" for n in body["nodes"] if n["id"] != uid_a or True) or not any(e["type"] == "CONNECTED_TO" and e["target"] == uid_b for e in body["edges"])
    # more precise: no connected edge
    assert not any(e["type"] == "CONNECTED_TO" and e["target"] == uid_b for e in body["edges"])


def test_graph_rejected_not_appears(client, alice, bob, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _add_connection(db_session, uid_a, uid_b, cm.ConnectionStatus.REJECTED)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    assert not any(e["type"] == "CONNECTED_TO" and e["target"] == uid_b for e in body["edges"])


def test_graph_no_recursive_expansion(client, alice, bob, carol, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _, uid_c = carol
    # A connected to B, B connected to C, but C should not appear in A's graph
    _add_connection(db_session, uid_a, uid_b, cm.ConnectionStatus.ACCEPTED)
    _add_connection(db_session, uid_b, uid_c, cm.ConnectionStatus.ACCEPTED)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    assert any(n["id"] == uid_b for n in body["nodes"])
    assert not any(n["id"] == uid_c for n in body["nodes"])
    assert not any(e["target"] == uid_c for e in body["edges"])


def test_graph_connected_visibility_respects_public(client, alice, bob, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _add_connection(db_session, uid_a, uid_b, cm.ConnectionStatus.ACCEPTED)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    bob_node = next(n for n in body["nodes"] if n["id"] == uid_b)
    # Should expose display_name but not private email
    assert bob_node["label"] == "Bob"
    assert bob_node["metadata"]["display_name"] == "Bob"
    assert "bob@test.edu" not in str(body)


# ---- Isolation ----

def test_graph_other_university_not_appear(client, alice, other_university, db_session, class_id):
    token_a, uid_a = alice
    # create user in other university with skill and forum that should not leak
    other_cls = db_session.scalar(select(m.Class).where(m.Class.name == "MATH-2024-A"))
    token_o, uid_o = _register(client, other_university, str(other_cls.id), email="othergraph2@othergraph.edu", student_no="OUT-002", enrollment_code="OTHER123", display_name="OtherGraph")
    # add skill to other user
    _add_skill(db_session, uid_o, "other-uni-skill")
    # create forum in other uni and join
    other_forum = _create_forum(db_session, str(other_cls.id), "Other Forum", fm.ForumStatus.APPROVED, uid_o)
    _join_forum(db_session, other_forum.id, uid_o)
    # connection pending between alice and other (should not appear)
    # but cross-university connections are forbidden at creation, so we insert directly to test isolation
    _add_connection(db_session, uid_a, uid_o, cm.ConnectionStatus.ACCEPTED)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    # Cross-uni skill/forum/dept must not appear, and cross-uni connection must be filtered
    assert not any(n["label"] == "other-uni-skill" for n in body["nodes"])
    assert not any(n["id"] == str(other_forum.id) for n in body["nodes"])
    assert not any(n["id"] == uid_o for n in body["nodes"])
    assert not any(e["target"] == uid_o for e in body["edges"])
    # University node should still be Test University, not Other University
    uni_labels = [n["label"] for n in body["nodes"] if n["type"] == "UNIVERSITY"]
    assert "Test University" in uni_labels
    assert "Other University" not in uni_labels


# ---- Graph correctness ----

def test_graph_no_duplicates_and_valid(client, alice, bob, db_session):
    token_a, uid_a = alice
    _, uid_b = bob
    _add_skill(db_session, uid_a, "python")
    _add_interest(db_session, uid_a, "robotics")
    forum = _create_forum(db_session, db_session.scalar(select(m.Class).where(m.Class.name == "CS-2024-A")).id, "Dup Forum", fm.ForumStatus.APPROVED, uid_a)
    _join_forum(db_session, forum.id, uid_a)
    _add_connection(db_session, uid_a, uid_b, cm.ConnectionStatus.ACCEPTED)
    db_session.commit()
    resp = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    body = resp.json()
    # no duplicate nodes
    ids = [n["id"] for n in body["nodes"]]
    assert len(ids) == len(set(ids))
    # no duplicate edges
    edge_ids = [e["id"] for e in body["edges"]]
    assert len(edge_ids) == len(set(edge_ids))
    # every edge points to existing node
    node_ids = set(ids)
    for e in body["edges"]:
        assert e["source"] in node_ids
        assert e["target"] in node_ids
    # root exists
    assert body["root_id"] == uid_a
    assert any(n["id"] == uid_a for n in body["nodes"])
    # valid types
    valid_node_types = {"STUDENT", "UNIVERSITY", "DEPARTMENT", "PROGRAM", "BATCH", "CLASS", "FORUM", "SKILL", "INTEREST"}
    valid_edge_types = {"BELONGS_TO", "ENROLLED_IN", "IN_PROGRAM", "IN_BATCH", "IN_CLASS", "MEMBER_OF", "PARTICIPATES_IN", "HAS_SKILL", "HAS_INTEREST", "CONNECTED_TO"}
    for n in body["nodes"]:
        assert n["type"] in valid_node_types
    for e in body["edges"]:
        assert e["type"] in valid_edge_types
    # deterministic: second call same
    resp2 = client.get("/api/v1/graph/me", headers=auth_headers(token_a))
    assert resp2.json() == body
