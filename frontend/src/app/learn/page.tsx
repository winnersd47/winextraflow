"use client";

/**
 * Lessons — the landing page for Telegram teasers.
 *
 * One route, not `/learn/[slug]`: the static export cannot build dynamic routes
 * (the same limitation that keeps `/dashboard/signals/[id]` out of the Pages build),
 * and a Telegram link must not break depending on how the frontend was deployed.
 * So the article is selected by `?a=<slug>` and fetched client-side.
 *
 * Public, no auth: requiring a login would end the funnel at the door.
 */

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

type Card = {
  slug: string;
  title: string;
  topic_ru: string;
  teaser: string;
  views: number;
};

type Full = Card & { body: string };

const TOPIC_STYLE: Record<string, string> = {
  Риск: "bg-red-500/10 text-red-400",
  Методика: "bg-brand-500/10 text-brand-500",
  Статистика: "bg-blue-500/10 text-blue-400",
  Рынки: "bg-purple-500/10 text-purple-400",
};

/** Minimal markdown: headings, bold, inline code, tables, lists, paragraphs. */
function renderBody(md: string): JSX.Element[] {
  const out: JSX.Element[] = [];
  const lines = md.split("\n");
  let i = 0;
  let key = 0;

  const inline = (t: string) =>
    t
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, '<code class="rounded bg-surface-hover px-1 text-xs">$1</code>');

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) { i++; continue; }

    if (line.startsWith("### ")) {
      out.push(<h3 key={key++} className="mt-5 mb-2 font-bold text-text-primary">{line.slice(4)}</h3>);
      i++; continue;
    }
    if (line.startsWith("## ")) {
      out.push(<h2 key={key++} className="mt-6 mb-2 text-lg font-bold text-text-primary">{line.slice(3)}</h2>);
      i++; continue;
    }
    if (line.startsWith("# ")) {
      i++; continue;                     // the title is already rendered above
    }

    if (line.startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push(
        <pre key={key++} className="my-3 overflow-x-auto rounded-lg bg-surface-hover p-3 text-xs text-text-secondary">
          <code>{buf.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // Table: header row, separator, body rows.
    if (line.startsWith("|") && lines[i + 1]?.includes("---")) {
      const cells = (r: string) => r.split("|").slice(1, -1).map(c => c.trim());
      const head = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(cells(lines[i++]));
      out.push(
        <div key={key++} className="my-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {head.map((h, n) => (
                  <th key={n} className="px-2 py-1.5 text-left font-medium text-text-muted"
                      dangerouslySetInnerHTML={{ __html: inline(h) }} />
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, n) => (
                <tr key={n} className="border-b border-border/40">
                  {r.map((c, m) => (
                    <td key={m} className="px-2 py-1.5 text-text-secondary"
                        dangerouslySetInnerHTML={{ __html: inline(c) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (/^[-*] /.test(line) || /^\d+\. /.test(line)) {
      const ordered = /^\d+\. /.test(line);
      const items: string[] = [];
      while (i < lines.length && (/^[-*] /.test(lines[i]) || /^\d+\. /.test(lines[i]))) {
        items.push(lines[i].replace(/^([-*]|\d+\.) /, ""));
        i++;
      }
      const List = ordered ? "ol" : "ul";
      out.push(
        <List key={key++} className={`my-2 space-y-1 pl-5 text-sm text-text-secondary ${ordered ? "list-decimal" : "list-disc"}`}>
          {items.map((it, n) => <li key={n} dangerouslySetInnerHTML={{ __html: inline(it) }} />)}
        </List>
      );
      continue;
    }

    out.push(
      <p key={key++} className="my-2 text-sm leading-relaxed text-text-secondary"
         dangerouslySetInnerHTML={{ __html: inline(line) }} />
    );
    i++;
  }
  return out;
}

function LearnContent() {
  const params = useSearchParams();
  const slug = params.get("a");
  const [cards, setCards] = useState<Card[]>([]);
  const [article, setArticle] = useState<Full | null>(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setMissing(false);

    /**
     * API first, bundled snapshot second.
     *
     * On the static export there is no backend, so the API call fails and the page
     * would show "материал не найден" — which reads as our content being broken
     * rather than absent. lessons.json is written into the build by
     * backend/scripts/export_lessons.py, so the article renders with no server at
     * all. When a backend IS reachable it wins, because that path counts views.
     */
    const fromApi = async () => {
      const r = await fetch(slug ? `/api/v1/lessons/${slug}` : "/api/v1/lessons");
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    };

    const fromBundle = async () => {
      const r = await fetch("/lessons.json");
      if (!r.ok) throw new Error("no snapshot");
      const d = await r.json();
      if (!slug) return d;
      const found = (d.lessons || []).find((l: Full) => l.slug === slug);
      if (!found) throw new Error("not in snapshot");
      return found;
    };

    (async () => {
      let data: any = null;
      try {
        data = await fromApi();
      } catch {
        try {
          data = await fromBundle();
        } catch {
          data = null;
        }
      }
      if (!alive) return;
      if (!data) setMissing(true);
      else if (slug) setArticle(data);
      else setCards(data.lessons || []);
      setLoading(false);
    })();

    return () => { alive = false; };
  }, [slug]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  if (slug) {
    if (missing || !article) {
      return (
        <div className="py-16 text-center">
          <p className="text-text-secondary">Материал не найден.</p>
          <Link href="/learn" className="mt-3 inline-block text-sm text-brand-500 hover:underline">
            ← Все материалы
          </Link>
        </div>
      );
    }
    return (
      <article className="mx-auto max-w-2xl px-4 py-8">
        <Link href="/learn" className="text-sm text-brand-500 hover:underline">← Все материалы</Link>
        <span className={`ml-3 rounded px-2 py-0.5 text-xs ${TOPIC_STYLE[article.topic_ru] || "bg-surface-hover text-text-muted"}`}>
          {article.topic_ru}
        </span>
        <h1 className="mt-3 text-2xl font-bold text-text-primary">{article.title}</h1>
        <div className="mt-4">{renderBody(article.body)}</div>
        <div className="mt-8 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-3 text-xs text-yellow-400/80">
          Материал носит образовательный характер и не является инвестиционной
          рекомендацией. Примеры взяты из собственных ошибок платформы — числа в них
          проверяемы по журналу сделок.
        </div>
      </article>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-bold text-text-primary">Материалы</h1>
      <p className="mt-1 text-sm text-text-secondary">
        Каждый разбор — из ошибки, которую платформа совершила и измерила. Числа
        сходятся с журналом сделок.
      </p>
      {cards.length === 0 ? (
        <p className="py-12 text-center text-sm text-text-muted">Материалов пока нет.</p>
      ) : (
        <div className="mt-5 space-y-3">
          {cards.map(c => (
            <Link key={c.slug} href={`/learn?a=${c.slug}`}
                  className="block rounded-xl border border-border bg-surface-card p-4 transition hover:border-brand-500/40">
              <span className={`rounded px-2 py-0.5 text-xs ${TOPIC_STYLE[c.topic_ru] || "bg-surface-hover text-text-muted"}`}>
                {c.topic_ru}
              </span>
              <h2 className="mt-2 font-bold text-text-primary">{c.title}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-text-secondary">
                {c.teaser.split("\n")[0]}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LearnPage() {
  // useSearchParams needs a Suspense boundary or the prerender fails.
  return (
    <Suspense fallback={<div className="py-20 text-center text-sm text-text-muted">Загрузка…</div>}>
      <LearnContent />
    </Suspense>
  );
}
