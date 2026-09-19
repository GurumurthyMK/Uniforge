import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "UniForge",
  description: "Verified university digital ecosystem.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
        <AuthProvider>
          <NavBar />
          <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
