import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UniForge",
  description: "Verified university digital ecosystem (MVP shell).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
        <header className="border-b bg-white">
          <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
            <span className="font-semibold">UniForge</span>
            <nav className="flex gap-4 text-sm text-zinc-600">
              <a className="hover:text-zinc-900" href="/">Home</a>
              <a className="hover:text-zinc-900" href="/health">Health</a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
