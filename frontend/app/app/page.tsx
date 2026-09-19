"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import { fetchMyProfile, type FullProfile } from "@/lib/api";
import { Loading } from "@/components/ui";
import { StatusBadge } from "@/components/ui";
import { AcademicBreadcrumb } from "@/components/VerifiedIdentityCard";

const ADMIN_ROLES = ["UNIVERSITY_ADMIN", "DEPARTMENT_ADMIN"];

function Dashboard() {
  const auth = useAuth();
  const [profile, setProfile] = useState<FullProfile | null>(null);

  const token = auth.status === "authenticated" ? auth.token : null;
  const me = auth.status === "authenticated" ? auth.me : null;

  useEffect(() => {
    if (!token) return;
    fetchMyProfile(token).then(setProfile).catch(() => setProfile(null));
  }, [token]);

  if (!me || !token) return null;
  const primary = [...me.identities].sort((a, b) => (a.status === "VERIFIED" ? -1 : 1))[0];
  const isAdmin = me.identities.some((i) => i.status === "VERIFIED" && ADMIN_ROLES.includes(i.role));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Welcome, {me.profile.display_name ?? me.email}</h1>
          {profile?.academic_context ? (
            <div className="mt-1">
              <AcademicBreadcrumb ctx={profile.academic_context} />
            </div>
          ) : (
            <p className="mt-1 text-sm text-zinc-600">{me.email}</p>
          )}
        </div>
        <button
          onClick={() => void auth.signOut()}
          className="rounded border px-3 py-1.5 text-sm hover:bg-zinc-100"
        >
          Log out
        </button>
      </div>

      {primary && primary.status !== "VERIFIED" && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          Your university identity is <StatusBadge status={primary.status} /> — an admin is reviewing
          your enrollment. Some areas unlock after verification.
        </p>
      )}

      <nav className="grid gap-4 sm:grid-cols-2" aria-label="Your spaces">
        <Card
          href="/app/profile"
          title="My profile"
          hint="Verified identity + your editable profile, skills and interests."
        />
        {primary?.class_id && (
          <Card href="/app/class" title="My class" hint="Class context, representative and classmates." />
        )}
        <Card href="/app/connections" title="Connections" hint="Your network, incoming and sent requests." />
        <Card href="/app/network" title="Your University Network" hint="Academic context, forums, skills, interests and connections in one graph." />
        {isAdmin && (
          <Card href="/app/admin" title="Structure admin" hint="Inspect and manage the academic hierarchy." />
        )}
      </nav>

      {profile && profile.skills.length + profile.interests.length > 0 && (
        <section className="rounded-lg border bg-white p-4 text-sm">
          <h2 className="font-medium">Your talent footprint</h2>
          <p className="mt-1 text-zinc-600">
            {profile.skills.length} skill{profile.skills.length === 1 ? "" : "s"} · {profile.interests.length}{" "}
            interest{profile.interests.length === 1 ? "" : "s"}/hobb{profile.interests.length === 1 ? "y" : "ies"}
          </p>
          <Link href="/app/profile" className="mt-2 inline-block underline">
            Manage them on your profile
          </Link>
        </section>
      )}
      {(!profile || profile.skills.length + profile.interests.length === 0) && (
        <section className="rounded-lg border border-dashed bg-white p-4 text-sm">
          <h2 className="font-medium">Build your talent footprint</h2>
          <p className="mt-1 text-zinc-600">
            Add skills, interests and hobbies so classmates with shared passions can find you.
          </p>
          <Link href="/app/profile/edit" className="mt-2 inline-block underline">
            Add them now
          </Link>
        </section>
      )}
    </div>
  );
}

function Card({ href, title, hint }: { href: string; title: string; hint: string }) {
  return (
    <Link href={href} className="rounded-lg border bg-white p-4 hover:border-zinc-400">
      <span className="font-medium">{title}</span>
      <span className="mt-1 block text-sm text-zinc-600">{hint}</span>
    </Link>
  );
}

export default function AppPage() {
  return (
    <RequireAuth>
      <Dashboard />
    </RequireAuth>
  );
}
