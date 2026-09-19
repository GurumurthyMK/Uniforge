"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export function NavBar() {
  const auth = useAuth();
  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <Link href="/" className="font-semibold">UniForge</Link>
        <nav className="flex items-center gap-4 text-sm text-zinc-600">
          <Link className="hover:text-zinc-900" href="/">Home</Link>
          <Link className="hover:text-zinc-900" href="/health">Health</Link>
          {auth.status === "authenticated" ? (
            <>
              <Link className="hover:text-zinc-900" href="/app">My space</Link>
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
