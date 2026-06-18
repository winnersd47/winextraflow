/**
 * Simple SWR-like cache for API responses.
 * Stale-while-revalidate: return cached data instantly, refresh in background.
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const cache = new Map<string, CacheEntry<any>>();

const DEFAULT_TTL = 30_000; // 30 seconds

/**
 * Fetch with cache. Returns cached data if fresh, refetches in background if stale.
 */
export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl: number = DEFAULT_TTL,
): Promise<T> {
  const cached = cache.get(key);
  const now = Date.now();

  // Fresh cache — return immediately
  if (cached && now - cached.timestamp < ttl) {
    return cached.data;
  }

  // Stale cache — return stale data but refresh in background
  if (cached) {
    fetcher().then(data => {
      cache.set(key, { data, timestamp: Date.now() });
    }).catch(() => {});
    return cached.data;
  }

  // No cache — fetch and store
  const data = await fetcher();
  cache.set(key, { data, timestamp: now });
  return data;
}

/**
 * Invalidate a specific cache key or all keys matching a prefix.
 */
export function invalidateCache(keyOrPrefix?: string) {
  if (!keyOrPrefix) {
    cache.clear();
    return;
  }
  for (const key of cache.keys()) {
    if (key === keyOrPrefix || key.startsWith(keyOrPrefix)) {
      cache.delete(key);
    }
  }
}

/**
 * Get cache stats for debugging.
 */
export function cacheStats() {
  return {
    size: cache.size,
    keys: Array.from(cache.keys()),
  };
}
