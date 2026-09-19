"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth, useAuth } from "@/lib/auth";
import {
  ApiError,
  listMyConnections,
  listIncomingRequests,
  listOutgoingRequests,
  acceptConnection,
  rejectConnection,
  cancelConnectionRequest,
  removeConnection,
  type ConnectionUser,
} from "@/lib/api";
import { EmptyState, Loading, buttonPrimaryClass, buttonSecondaryClass } from "@/components/ui";

function UserRow({
  user,
  actions,
  busy,
  onAction,
}: {
  user: ConnectionUser;
  actions: ("accept" | "reject" | "cancel" | "remove" | "view")[];
  busy: boolean;
  onAction: (id: string, action: string) => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <Link href={`/app/people/${user.user_id}`} className="font-medium underline text-sm">
        {user.display_name ?? "Unnamed student"}
      </Link>
      <div className="flex gap-1">
        {actions.includes("accept") && (
          <button disabled={busy} onClick={() => onAction(user.user_id, "accept")} className="rounded bg-zinc-900 px-2.5 py-1 text-xs text-white disabled:opacity-50">
            Accept
          </button>
        )}
        {actions.includes("reject") && (
          <button disabled={busy} onClick={() => onAction(user.user_id, "reject")} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">
            Reject
          </button>
        )}
        {actions.includes("cancel") && (
          <button disabled={busy} onClick={() => onAction(user.user_id, "cancel")} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">
            Cancel
          </button>
        )}
        {actions.includes("remove") && (
          <button disabled={busy} onClick={() => onAction(user.user_id, "remove")} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">
            Remove
          </button>
        )}
        {actions.includes("view") && (
          <Link href={`/app/people/${user.user_id}`} className="rounded border px-2.5 py-1 text-xs hover:bg-zinc-100">
            View
          </Link>
        )}
      </div>
    </li>
  );
}

function ConnectionsPageInner() {
  const auth = useAuth();
  const token = auth.status === "authenticated" ? auth.token : null;
  const [conns, setConns] = useState<ConnectionUser[] | null>(null);
  const [incoming, setIncoming] = useState<ConnectionUser[] | null>(null);
  const [outgoing, setOutgoing] = useState<ConnectionUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    if (!token) return;
    Promise.all([listMyConnections(token), listIncomingRequests(token), listOutgoingRequests(token)])
      .then(([c, inc, out]) => {
        setConns(c);
        setIncoming(inc);
        setOutgoing(out);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load connections."));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handle = async (userId: string, action: string) => {
    if (!token) return;
    setBusyId(userId);
    try {
      if (action === "accept") await acceptConnection(token, userId);
      else if (action === "reject") await rejectConnection(token, userId);
      else if (action === "cancel") await cancelConnectionRequest(token, userId);
      else if (action === "remove") await removeConnection(token, userId);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusyId(null);
    }
  };

  if (error) return <p className="text-sm text-red-700" role="alert">{error}</p>;
  if (conns === null || incoming === null || outgoing === null) return <Loading label="Loading connections…" />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Connections</h1>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium">My Connections ({conns.length})</h2>
        {conns.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No connections yet. Discover classmates in your class.</p>
        ) : (
          <ul className="mt-3 divide-y">
            {conns.map((u) => (
              <UserRow key={u.user_id} user={u} actions={["remove", "view"]} busy={busyId === u.user_id} onAction={handle} />
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium">Incoming Requests ({incoming.length})</h2>
        {incoming.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No incoming requests.</p>
        ) : (
          <ul className="mt-3 divide-y">
            {incoming.map((u) => (
              <UserRow key={u.user_id} user={u} actions={["accept", "reject"]} busy={busyId === u.user_id} onAction={handle} />
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium">Sent Requests ({outgoing.length})</h2>
        {outgoing.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No pending sent requests.</p>
        ) : (
          <ul className="mt-3 divide-y">
            {outgoing.map((u) => (
              <UserRow key={u.user_id} user={u} actions={["cancel"]} busy={busyId === u.user_id} onAction={handle} />
            ))}
          </ul>
        )}
      </section>

      <p className="text-sm text-zinc-500">
        Tip: Find classmates on the <Link href="/app/class" className="underline">Class</Link> page and send them a connection request.
      </p>
    </div>
  );
}

export default function ConnectionsRoute() {
  return (
    <RequireAuth>
      <ConnectionsPageInner />
    </RequireAuth>
  );
}
