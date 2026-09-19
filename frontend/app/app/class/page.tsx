"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth, useAuth } from "@/lib/auth";
import {
  ApiError,
  fetchClassDetail,
  fetchClassMembers,
  joinForum,
  leaveForum,
  listClassForums,
  listForumProposals,
  proposeForum,
  reviewForum,
  listMyConnections,
  listIncomingRequests,
  listOutgoingRequests,
  sendConnectionRequest,
  acceptConnection,
  rejectConnection,
  cancelConnectionRequest,
  removeConnection,
  type ClassDetail,
  type ClassMembersPage,
  type Forum,
} from "@/lib/api";
import { EmptyState, Loading, StatusBadge, Field, buttonPrimaryClass, buttonSecondaryClass, inputClass } from "@/components/ui";

const PAGE_SIZE = 30;

function ForumCard({ forum, onJoin, onLeave, busy }: { forum: Forum; onJoin: () => void; onLeave: () => void; busy: boolean }) {
  const badge =
    forum.status === "APPROVED" ? "bg-green-100 text-green-800" : forum.status === "PENDING" ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium">
            {forum.status === "APPROVED" ? (
              <Link href={`/app/forums/${forum.id}`} className="underline hover:text-zinc-700">{forum.name}</Link>
            ) : (
              forum.name
            )}
          </h3>
          {forum.description && <p className="mt-1 text-sm text-zinc-600">{forum.description}</p>}
          <p className="mt-2 text-xs text-zinc-500">
            {forum.member_count} member{forum.member_count === 1 ? "" : "s"} · <span className={`rounded px-1.5 py-0.5 text-xs ${badge}`}>{forum.status}</span>
            {forum.is_member && <span className="ml-2 text-green-700">· Joined</span>}
          </p>
          {forum.status === "APPROVED" && (
            <Link href={`/app/forums/${forum.id}`} className="mt-2 inline-block text-xs text-zinc-600 underline">Open forum →</Link>
          )}
        </div>
        {forum.status === "APPROVED" && (
          <div className="shrink-0">
            {forum.is_member ? (
              <button disabled={busy} onClick={onLeave} className={buttonSecondaryClass}>
                Leave
              </button>
            ) : (
              <button disabled={busy} onClick={onJoin} className={buttonPrimaryClass}>
                Join
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ClassPage() {
  const auth = useAuth();
  const [detail, setDetail] = useState<ClassDetail | null>(null);
  const [page, setPage] = useState<ClassMembersPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [forums, setForums] = useState<Forum[] | null>(null);
  const [proposals, setProposals] = useState<Forum[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forumError, setForumError] = useState<string | null>(null);
  const [proposeName, setProposeName] = useState("");
  const [proposeDesc, setProposeDesc] = useState("");
  const [busyForum, setBusyForum] = useState<string | null>(null);
  const [proposeBusy, setProposeBusy] = useState(false);
  const [connMap, setConnMap] = useState<Record<string, "CONNECTED" | "PENDING_OUTGOING" | "PENDING_INCOMING" | "NONE">>({});
  const [busyConn, setBusyConn] = useState<string | null>(null);
  const [connError, setConnError] = useState<string | null>(null);

  const token = auth.status === "authenticated" ? auth.token : null;
  const me = auth.status === "authenticated" ? auth.me : null;
  const classId =
    auth.status === "authenticated"
      ? auth.me.identities.find((i) => i.status === "VERIFIED" && i.class_id)?.class_id ?? null
      : null;
  const isRep =
    auth.status === "authenticated" &&
    !!auth.me.identities.find((i) => i.status === "VERIFIED" && i.class_id === classId && i.role === "CLASS_REP");

  const loadForums = () => {
    if (!token || !classId) return;
    listClassForums(token, classId)
      .then(setForums)
      .catch((e) => setForumError(e instanceof ApiError ? e.message : "Could not load forums."));
    if (isRep) {
      listForumProposals(token, classId)
        .then(setProposals)
        .catch(() => setProposals([]));
    }
  };

  useEffect(() => {
    if (!token || !classId) return;
    fetchClassDetail(token, classId)
      .then(setDetail)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load class."));
  }, [token, classId]);

  useEffect(() => {
    if (!token || !classId) return;
    fetchClassMembers(token, classId, PAGE_SIZE, offset)
      .then(setPage)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load members."));
  }, [token, classId, offset]);

  const loadConnections = () => {
    if (!token) return;
    Promise.all([listMyConnections(token), listIncomingRequests(token), listOutgoingRequests(token)])
      .then(([conns, incoming, outgoing]) => {
        const m: Record<string, "CONNECTED" | "PENDING_OUTGOING" | "PENDING_INCOMING" | "NONE"> = {};
        conns.forEach((c) => (m[c.user_id] = "CONNECTED"));
        incoming.forEach((c) => (m[c.user_id] = "PENDING_INCOMING"));
        outgoing.forEach((c) => (m[c.user_id] = "PENDING_OUTGOING"));
        setConnMap(m);
      })
      .catch(() => setConnMap({}));
  };

  useEffect(() => {
    loadForums();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, classId, isRep]);

  useEffect(() => {
    loadConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleConn = async (userId: string, action: string) => {
    if (!token) return;
    setBusyConn(userId);
    setConnError(null);
    try {
      if (action === "connect") await sendConnectionRequest(token, userId);
      else if (action === "cancel") await cancelConnectionRequest(token, userId);
      else if (action === "accept") await acceptConnection(token, userId);
      else if (action === "reject") await rejectConnection(token, userId);
      else if (action === "remove") await removeConnection(token, userId);
      loadConnections();
    } catch (e) {
      setConnError(e instanceof ApiError ? e.message : "Connection action failed.");
    } finally {
      setBusyConn(null);
    }
  };

  if (auth.status !== "authenticated") return null;
  if (error) return <p className="text-sm text-red-700" role="alert">{error}</p>;
  if (!classId) {
    return <EmptyState title="No class assigned" hint="Your verified identity is not linked to a class yet." />;
  }
  if (!detail || !page) return <Loading label="Loading your class…" />;

  const totalPages = Math.max(1, Math.ceil(page.total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const handlePropose = async () => {
    if (!token || !classId || !proposeName.trim()) return;
    setProposeBusy(true);
    setForumError(null);
    try {
      await proposeForum(token, classId, { name: proposeName.trim(), description: proposeDesc.trim() || null });
      setProposeName("");
      setProposeDesc("");
      loadForums();
    } catch (e) {
      setForumError(e instanceof ApiError ? e.message : "Proposal failed.");
    } finally {
      setProposeBusy(false);
    }
  };

  const handleJoin = async (fid: string) => {
    if (!token) return;
    setBusyForum(fid);
    try {
      await joinForum(token, fid);
      loadForums();
    } catch (e) {
      setForumError(e instanceof ApiError ? e.message : "Join failed.");
    } finally {
      setBusyForum(null);
    }
  };
  const handleLeave = async (fid: string) => {
    if (!token) return;
    setBusyForum(fid);
    try {
      await leaveForum(token, fid);
      loadForums();
    } catch (e) {
      setForumError(e instanceof ApiError ? e.message : "Leave failed.");
    } finally {
      setBusyForum(null);
    }
  };
  const handleReview = async (fid: string, status: "APPROVED" | "REJECTED") => {
    if (!token) return;
    setBusyForum(fid);
    try {
      await reviewForum(token, fid, status);
      loadForums();
    } catch (e) {
      setForumError(e instanceof ApiError ? e.message : "Review failed.");
    } finally {
      setBusyForum(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wide text-zinc-500">My class</p>
        <h1 className="text-2xl font-bold">{detail.class.name}</h1>
        <p className="mt-1 text-sm text-zinc-600">
          {detail.program.name} · Batch {detail.batch.name} · {detail.department.name} · {detail.university.name}
        </p>
      </div>

      {detail.class_rep && (
        <section className="rounded-lg border bg-white p-4 text-sm">
          <h2 className="font-medium">Class representative</h2>
          <Link href={`/app/people/${detail.class_rep.user_id}`} className="mt-1 inline-block font-medium text-zinc-900 underline">
            {detail.class_rep.display_name ?? "Class rep"}
          </Link>
        </section>
      )}

      <section className="rounded-lg border bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Class forums</h2>
          <span className="text-xs text-zinc-500">{forums ? `${forums.length} approved` : "loading…"}</span>
        </div>
        {forumError && <p className="mt-2 text-sm text-red-700" role="alert">{forumError}</p>}
        {forums === null ? (
          <p className="mt-2 text-sm text-zinc-500">Loading forums…</p>
        ) : forums.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No forums yet. Propose one below.</p>
        ) : (
          <div className="mt-3 grid gap-3">
            {forums.map((f) => (
              <ForumCard key={f.id} forum={f} busy={busyForum === f.id} onJoin={() => handleJoin(f.id)} onLeave={() => handleLeave(f.id)} />
            ))}
          </div>
        )}

        <div className="mt-6 rounded border border-dashed p-4">
          <h3 className="text-sm font-medium">Propose a forum</h3>
          <p className="mt-1 text-xs text-zinc-500">Visible to your class only. Reviewed by the class representative.</p>
          <div className="mt-3 grid gap-3">
            <Field label="Forum name">
              <input className={inputClass} value={proposeName} onChange={(e) => setProposeName(e.target.value)} placeholder="e.g. Exam Prep" maxLength={100} />
            </Field>
            <Field label="Description (optional)">
              <textarea className={inputClass} value={proposeDesc} onChange={(e) => setProposeDesc(e.target.value)} placeholder="What is this forum for?" rows={2} maxLength={2000} />
            </Field>
            <button disabled={proposeBusy || !proposeName.trim()} onClick={handlePropose} className={buttonPrimaryClass + " w-fit"}>
              {proposeBusy ? "Proposing…" : "Propose forum"}
            </button>
          </div>
        </div>

        {isRep && (
          <div className="mt-6 rounded border bg-amber-50 p-4">
            <h3 className="text-sm font-medium">Proposals to review (Class Rep)</h3>
            {proposals === null ? (
              <p className="mt-2 text-sm text-zinc-500">Loading proposals…</p>
            ) : proposals.length === 0 ? (
              <p className="mt-2 text-sm text-zinc-600">No pending proposals.</p>
            ) : (
              <div className="mt-3 grid gap-3">
                {proposals.map((p) => (
                  <div key={p.id} className="rounded border bg-white p-3">
                    <p className="font-medium text-sm">{p.name}</p>
                    {p.description && <p className="text-sm text-zinc-600">{p.description}</p>}
                    <div className="mt-2 flex gap-2">
                      <button disabled={busyForum === p.id} onClick={() => handleReview(p.id, "APPROVED")} className={buttonPrimaryClass}>
                        Approve
                      </button>
                      <button disabled={busyForum === p.id} onClick={() => handleReview(p.id, "REJECTED")} className={buttonSecondaryClass}>
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Classmates ({page.total})</h2>
        </div>
        {connError && <p className="mt-2 text-sm text-red-700" role="alert">{connError}</p>}
        {page.items.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No verified members yet.</p>
        ) : (
          <ul className="mt-3 divide-y text-sm">
            {page.items.map((m) => {
              const isSelf = me?.id === m.user_id;
              const status = isSelf ? "SELF" : connMap[m.user_id] ?? "NONE";
              return (
                <li key={m.user_id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2">
                    <Link href={`/app/people/${m.user_id}`} className="font-medium underline">
                      {m.display_name ?? "Unnamed student"}
                    </Link>
                    <span className="flex items-center gap-2 text-xs text-zinc-500">
                      {m.role !== "STUDENT" && <span>{m.role}</span>}
                      <StatusBadge status={m.verification_status} />
                    </span>
                  </div>
                  {!isSelf && (
                    <div className="flex flex-wrap gap-1">
                      {status === "NONE" && (
                        <button disabled={busyConn === m.user_id} onClick={() => handleConn(m.user_id, "connect")} className="rounded bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50">
                          Connect
                        </button>
                      )}
                      {status === "PENDING_OUTGOING" && (
                        <>
                          <span className="rounded bg-amber-100 px-2.5 py-1 text-xs text-amber-900">Request Sent</span>
                          <button disabled={busyConn === m.user_id} onClick={() => handleConn(m.user_id, "cancel")} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">Cancel</button>
                        </>
                      )}
                      {status === "PENDING_INCOMING" && (
                        <>
                          <button disabled={busyConn === m.user_id} onClick={() => handleConn(m.user_id, "accept")} className="rounded bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50">Accept</button>
                          <button disabled={busyConn === m.user_id} onClick={() => handleConn(m.user_id, "reject")} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">Reject</button>
                        </>
                      )}
                      {status === "CONNECTED" && (
                        <>
                          <span className="rounded bg-green-100 px-2.5 py-1 text-xs text-green-800">Connected</span>
                          <button disabled={busyConn === m.user_id} onClick={() => handleConn(m.user_id, "remove")} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">Remove</button>
                        </>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center gap-3 text-sm">
            <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))} className="rounded border px-3 py-1 disabled:opacity-40">
              Previous
            </button>
            <span className="text-zinc-500">Page {currentPage} of {totalPages}</span>
            <button disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset((o) => o + PAGE_SIZE)} className="rounded border px-3 py-1 disabled:opacity-40">
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

export default function ClassRoutePage() {
  return (
    <RequireAuth>
      <ClassPage />
    </RequireAuth>
  );
}
