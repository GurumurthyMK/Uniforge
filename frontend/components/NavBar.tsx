"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

const ADMIN_ROLES = ["UNIVERSITY_ADMIN", "DEPARTMENT_ADMIN"];

export function NavBar() {
  const auth = useAuth();
  const isAdmin =
    auth.status === "authenticated" &&
    auth.me.identities.some((i) => i.status === "VERIFIED" && ADMIN_ROLES.includes(i.role));
  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <Link href="/" className="font-semibold">UniForge</Link>
        <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-600">
          <Link className="hover:text-zinc-900" href="/">Home</Link>
          <Link className="hover:text-zinc-900" href="/health">Health</Link>
          {auth.status === "authenticated" ? (
            <>
              <Link className="hover:text-zinc-900" href="/app">My space</Link>
              <Link className="hover:text-zinc-900" href="/app/profile">Profile</Link>
              <Link className="hover:text-zinc-900" href="/app/class">Class</Link>
              <Link className="hover:text-zinc-900" href="/app/notifications">Notifications</Link>
              {isAdmin && (
                <Link className="hover:text-zinc-900" href="/app/admin">Admin</Link>
              )}
              <button onClick={() => void auth.signOut()} className="hover:text-zinc-900">
                Log out
              </button>
            </>
          ) : (
            <>
              <Link className="hover:text-zinc-900" href="/login">Log in</Link>
              <Link className="hover:text-zinc-900" href="/register">Register</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
