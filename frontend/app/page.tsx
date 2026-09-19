import Link from "next/link";
import { ApiStatus } from "@/components/ApiStatus";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">UniForge — verified university ecosystem</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Verify your university identity, build your profile, and collaborate with
          students in your classes and clubs.
        </p>
      </div>
      <div className="flex gap-3 text-sm">
        <Link href="/register" className="rounded bg-zinc-900 px-4 py-2 font-medium text-white">
          Create account
        </Link>
        <Link href="/login" className="rounded border px-4 py-2 font-medium hover:bg-zinc-100">
          Log in
        </Link>
      </div>
      <div className="rounded-lg border bg-white p-4 text-sm">
        <p className="font-medium">Hackathon demo</p>
        <p className="mt-1 text-zinc-600">
          Log in as <code>ada@demo-university.edu</code> / <code>Demo1234!</code>, or register
          with a <code>@demo-university.edu</code> email and enrollment code{" "}
          <code>UNIFORGE-DEMO-2026</code> to become instantly verified.
        </p>
      </div>
      <ApiStatus />
    </div>
  );
}
