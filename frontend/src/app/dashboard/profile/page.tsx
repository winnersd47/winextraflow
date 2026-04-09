"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ProfileResponse, AchievementResponse } from "@/types";

const CATEGORIES = ["all", "trading", "social", "learning", "milestone"];

export default function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("all");

  useEffect(() => {
    async function load() {
      try {
        const p = await api.getProfile();
        setProfile(p);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  if (!profile) return null;

  const filtered =
    category === "all"
      ? profile.achievements
      : profile.achievements.filter((a) => a.category === category);

  return (
    <div className="mx-auto max-w-3xl">
      {/* User Header */}
      <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-500/20 text-3xl">
            {profile.xp.level >= 10 ? "💎" : profile.xp.level >= 5 ? "🌟" : "🎮"}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">{user?.username}</h1>
            <p className="text-sm text-gray-400">
              Level {profile.xp.level} &middot; {profile.xp.total_xp} XP &middot;{" "}
              {profile.unlocked_count}/{profile.total_count} achievements
            </p>
          </div>
        </div>

        {/* XP Progress Bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Level {profile.xp.level}</span>
            <span>Level {profile.xp.level + 1}</span>
          </div>
          <div className="mt-1 h-3 overflow-hidden rounded-full bg-gray-700">
            <div
              className="h-full rounded-full bg-brand-500 transition-all"
              style={{ width: `${Math.min(100, profile.xp.progress_pct)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-gray-500">
            {profile.xp.current_level_xp} / {profile.xp.next_level_xp} XP to next level
          </p>
        </div>
      </div>

      {/* Category Filter */}
      <div className="mb-4 flex gap-1">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`rounded-lg px-3 py-2 text-sm capitalize transition ${
              category === c
                ? "bg-brand-500/20 text-brand-500"
                : "text-gray-400 hover:bg-surface-hover hover:text-white"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Achievements Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {filtered.map((ach) => (
          <AchievementCard key={ach.id} achievement={ach} />
        ))}
      </div>
    </div>
  );
}

function AchievementCard({ achievement: a }: { achievement: AchievementResponse }) {
  const pct = a.requirement_value > 0 ? (a.progress / a.requirement_value) * 100 : 0;

  return (
    <div
      className={`rounded-xl border p-4 transition ${
        a.is_unlocked
          ? "border-brand-500/50 bg-brand-500/5"
          : "border-gray-800 bg-surface-card opacity-70"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl">{a.is_hidden && !a.is_unlocked ? "❓" : a.icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">
              {a.is_hidden && !a.is_unlocked ? "Hidden Achievement" : a.name}
            </h3>
            {a.is_unlocked && (
              <span className="rounded bg-brand-500/20 px-1.5 py-0.5 text-xs text-brand-500">
                Unlocked
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs text-gray-400">
            {a.is_hidden && !a.is_unlocked ? "???" : a.description}
          </p>
          {a.xp_reward > 0 && (
            <p className="mt-1 text-xs text-yellow-400">+{a.xp_reward} XP</p>
          )}
        </div>
      </div>

      {!a.is_unlocked && !a.is_hidden && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Progress</span>
            <span>
              {a.progress}/{a.requirement_value}
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-700">
            <div
              className="h-full rounded-full bg-brand-500/60"
              style={{ width: `${Math.min(100, pct)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
