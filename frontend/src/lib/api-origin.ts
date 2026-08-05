/**
 * Points relative /api/* calls at an external backend.
 *
 * In dev the Next.js rewrite proxies /api/* to localhost:8000, so relative URLs
 * work. In a static export (Cloudflare Pages) there is no server to rewrite, so
 * every /api/* call must be absolute.
 *
 * Rather than touching ~50 fetch call sites, this patches window.fetch once at
 * module load — before any component effect runs. Set NEXT_PUBLIC_API_URL at
 * build time (e.g. https://api.winextraflow.ru, no trailing slash); leave it
 * empty and nothing is patched.
 */

export const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

declare global {
  interface Window {
    __wefFetchPatched?: boolean;
  }
}

if (typeof window !== "undefined" && API_ORIGIN && !window.__wefFetchPatched) {
  window.__wefFetchPatched = true;
  const original = window.fetch.bind(window);

  const absolutize = (url: string): string =>
    url.startsWith("/api/") ? API_ORIGIN + url : url;

  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    try {
      if (typeof input === "string") {
        input = absolutize(input);
      } else if (input instanceof URL) {
        if (input.origin === window.location.origin && input.pathname.startsWith("/api/")) {
          input = new URL(API_ORIGIN + input.pathname + input.search);
        }
      } else if (input instanceof Request) {
        const u = new URL(input.url, window.location.origin);
        if (u.origin === window.location.origin && u.pathname.startsWith("/api/")) {
          input = new Request(API_ORIGIN + u.pathname + u.search, input);
        }
      }
    } catch {
      // Never break a request because rewriting failed
    }
    return original(input as RequestInfo, init);
  };
}
