"use client";

import { useEffect, useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import { ApiError, fetchMyProfile, type FullProfile } from "@/lib/api";
import { Loading } from "@/components/ui";
import { ProfileCard } from "@/components/ProfileCard";
import { VerifiedIdentityCard } from "@/components/VerifiedIdentityCard";

function MyProfile() {
  const auth = useAuth();
  const [profile, setProfile] = useState<FullProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const token = auth.status === "authenticated" ? auth.token : null;
  const identities = auth.status === "authenticated" ? auth.me.identities : [];

  useEffect(() => {
    if (!token) return;
    fetchMyProfile(token)
      .then(setProfile)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load profile."));
  }, [token]);

  if (auth.status !== "authenticated") return null;
  if (error) return <p className="text-sm text-red-700" role="alert">{error}</p>;
  if (!profile) return <Loading label="Loading your profile…" />;

  const primary = [...identities].sort((a, b) =>
    a.status === "VERIFIED" ? -1 : 1
  )[0];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">My profile</h1>
      {primary ? (
        <VerifiedIdentityCard identity={primary} />
      ) : (
        <p className="rounded-lg border bg-white p-4 text-sm text-zinc-500">No university identity yet.</p>
      )}
      <ProfileCard profile={profile} editable />
      <p className="text-xs text-zinc-500">
        Your identity card is university-controlled and read-only. Everything in your profile card is
        yours to edit — it is never treated as verified.
      </p>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <RequireAuth>
      <MyProfile />
    </RequireAuth>
  );
}
