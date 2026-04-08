"use client";

import { useAuth } from "@/lib/auth";

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-800 bg-surface-card px-6">
      <div />
      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-sm text-gray-400">{user.username}</span>
            <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs text-brand-500">
              {user.role}
            </span>
            <button
              onClick={logout}
              className="text-sm text-gray-400 transition hover:text-white"
            >
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  );
}
