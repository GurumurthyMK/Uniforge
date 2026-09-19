"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RequireAuth, useAuth } from "@/lib/auth";
import { ApiError, fetchPublicProfile, type PublicProfile } from "@/lib/api";
import { EmptyState, Loading, StatusBadge } from "@/components/ui";
import { AcademicBreadcrumb } from "@/components/VerifiedIdentityCard";
import { ProfileCard } from "@/components/ProfileCard";

function PublicProfileView() {
  const auth = useAuth();
  const params = useParams<{ id: string }>();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);

  const token = auth.status === "authenticated" ? auth.token : null;
  const id = params.id;

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
