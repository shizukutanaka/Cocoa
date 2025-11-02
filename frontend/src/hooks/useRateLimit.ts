import { useState, useEffect, useCallback } from 'react';

interface RateLimitOptions {
  maxRequests: number;
  windowMs: number;
}

export const useRateLimit = ({ maxRequests, windowMs }: RateLimitOptions) => {
  const [requests, setRequests] = useState<number[]>([]);
  const [isLimited, setIsLimited] = useState(false);

  const checkLimit = useCallback(() => {
    const now = Date.now();
    const windowStart = now - windowMs;

    // 時間枠内のリクエストをフィルタリング
    const recentRequests = requests.filter(time => time > windowStart);

    if (recentRequests.length >= maxRequests) {
      setIsLimited(true);
      return false;
    }

    setRequests([...recentRequests, now]);
    setIsLimited(false);
    return true;
  }, [requests, maxRequests, windowMs]);

  const reset = useCallback(() => {
    setRequests([]);
    setIsLimited(false);
  }, []);

  // 定期的に古いリクエストをクリーンアップ
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const windowStart = now - windowMs;
      setRequests(prev => prev.filter(time => time > windowStart));
    }, windowMs);

    return () => clearInterval(interval);
  }, [windowMs]);

  return { checkLimit, reset, isLimited };
};
