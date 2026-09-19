"use client";
import { useEffect, useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import { ApiError, listNotifications, markNotificationRead, type Notification } from "@/lib/api";
import { EmptyState, Loading } from "@/components/ui";

function NotificationsInner() {
  const auth = useAuth();
  const token = auth.status === "authenticated" ? auth.token : null;
  const [items, setItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!token) return;
    listNotifications(token, 50, 0).then(setItems).catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load."));
  }, [token]);
  const handleRead = async (id: string) => {
    if (!token) return;
    try {
      const updated = await markNotificationRead(token, id);
      setItems((prev) => prev ? prev.map((n) => n.id === id ? updated : n) : prev);
    } catch {}
  };
  if (!token) return null;
  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (items === null) return <Loading label="Loading notifications…" />;
  if (items.length === 0) return <EmptyState title="No notifications" hint="When someone comments on your post, it will appear here." />;
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">Notifications</h1>
      <ul className="space-y-2">
        {items.map((n) => (
          <li key={n.id} className={`rounded border p-3 text-sm ${n.is_read ? "bg-white" : "bg-amber-50 border-amber-200"}`}>
            <p>{n.message}</p>
            <p className="text-xs text-zinc-500 mt-1">{new Date(n.created_at).toLocaleString()} {n.is_read ? "· read" : "· unread"}</p>
            {!n.is_read && (
              <button onClick={() => handleRead(n.id)} className="mt-2 text-xs underline">Mark read</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <NotificationsInner />
    </RequireAuth>
  );
}
