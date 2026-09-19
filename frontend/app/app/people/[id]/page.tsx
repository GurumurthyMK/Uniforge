"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { RequireAuth, useAuth } from "@/lib/auth";
import {
  ApiError,
  fetchPublicProfile,
  fetchConnectionStatus,
  fetchMutuals,
  sendConnectionRequest,
  acceptConnection,
  rejectConnection,
  cancelConnectionRequest,
  removeConnection,
  type PublicProfile,
  type ConnectionStatusResp,
  type MutualsResp,
} from "@/lib/api";
import { EmptyState, Loading, StatusBadge, buttonPrimaryClass, buttonSecondaryClass } from "@/components/ui";
import { AcademicBreadcrumb } from "@/components/VerifiedIdentityCard";
import { ProfileCard } from "@/components/ProfileCard";

function ConnectionAction({ userId, token, isSelf }: { userId: string; token: string; isSelf: boolean }) {
  const [status, setStatus] = useState<ConnectionStatusResp | null>(null);
  const [mutuals, setMutuals] = useState<MutualsResp | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetchConnectionStatus(token, userId)
      .then(setStatus)
      .catch(() => setStatus({ status: "NONE", connection: null }));
    fetchMutuals(token, userId)
      .then(setMutuals)
      .catch(() => setMutuals({ count: 0, users: [] }));
  };

  useEffect(() => {
    if (isSelf) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, userId, isSelf]);

  if (isSelf) return null;
  if (!status) return <p className="text-sm text-zinc-500">Loading connection…</p>;

  const doAction = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="text-sm font-medium">Connection</h3>
      {error && <p className="mt-2 text-sm text-red-700" role="alert">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {status.status === "NONE" || status.status === "REJECTED" ? (
          <button disabled={busy} onClick={() => doAction(() => sendConnectionRequest(token, userId))} className={buttonPrimaryClass}>
            {busy ? "Sending…" : "Connect"}
          </button>
        ) : status.status === "PENDING_OUTGOING" ? (
          <>
            <span className="rounded bg-amber-100 px-3 py-2 text-sm text-amber-900">Request Sent</span>
            <button disabled={busy} onClick={() => doAction(() => cancelConnectionRequest(token, userId))} className={buttonSecondaryClass}>
              Cancel request
            </button>
          </>
        ) : status.status === "PENDING_INCOMING" ? (
          <>
            <button disabled={busy} onClick={() => doAction(() => acceptConnection(token, userId))} className={buttonPrimaryClass}>
              Accept
            </button>
            <button disabled={busy} onClick={() => doAction(() => rejectConnection(token, userId))} className={buttonSecondaryClass}>
              Reject
            </button>
          </>
        ) : status.status === "CONNECTED" ? (
          <>
            <span className="rounded bg-green-100 px-3 py-2 text-sm text-green-800">Connected</span>
            <button disabled={busy} onClick={() => doAction(() => removeConnection(token, userId))} className={buttonSecondaryClass}>
              Remove Connection
            </button>
          </>
        ) : null}
      </div>
      {mutuals && mutuals.count > 0 && (
        <p className="mt-3 text-sm text-zinc-600">
          {mutuals.count} mutual connection{mutuals.count === 1 ? "" : "s"}
          {mutuals.users.length > 0 && ": "}
          {mutuals.users.slice(0, 3).map((u) => u.display_name ?? "Student").join(", ")}
          {mutuals.count > 3 && " …"}
        </p>
      )}
      {mutuals && mutuals.count === 0 && <p className="mt-3 text-sm text-zinc-500">No mutual connections.</p>}
    </div>
  );
}

function PublicProfileView() {
  const auth = useAuth();
  const params = useParams<{ id: string }>();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);

  const token = auth.status === "authenticated" ? auth.token : null;
  const id = params.id;
  const isSelf = auth.status === "authenticated" && auth.me.id === id;

  useEffect(() => {
    if (!token || !id) return;
    fetchPublicProfile(token, id)
      .then(setProfile)
      .catch((e) =>
        setError({
          message: e instanceof ApiError ? e.message : "Could not load profile.",
          code: e instanceof ApiError ? e.code : undefined,
        })
      );
  }, [token, id]);

  if (auth.status !== "authenticated") return null;
  if (error) {
    return error.code === "FORBIDDEN" ? (
      <EmptyState
        title="Profile not visible"
        hint="Only verified members of the same university can view this profile."
      />
    ) : (
      <p className="text-sm text-red-700" role="alert">{error.message}</p>
    );
  }
  if (!profile) return <Loading label="Loading profile…" />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold">{profile.display_name ?? "Student"}</h1>
        <StatusBadge status={profile.verification_status} />
        <span className="text-sm text-zinc-500">{profile.role}</span>
      </div>
      {profile.academic_context && <AcademicBreadcrumb ctx={profile.academic_context} />}
      {token && <ConnectionAction userId={id} token={token} isSelf={isSelf} />}
      <ProfileCard profile={profile} />
    </div>
  );
}

export default function PeoplePage() {
  return (
    <RequireAuth>
      <PublicProfileView />
    </RequireAuth>
  );
}
