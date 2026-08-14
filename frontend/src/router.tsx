import { useEffect, useState, type AnchorHTMLAttributes, type MouseEvent } from "react";

export interface RouteLocation {
  /** 現在のパス */
  path: string;
  /** ?から始まるクエリ文字列 */
  search: string;
  /** #から始まるページ内リンク */
  hash: string;
}

function readLocation(): RouteLocation {
  return { path: window.location.pathname, search: window.location.search, hash: window.location.hash };
}

const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

export function navigate(to: string, options?: { replace?: boolean }): void {
  if (options?.replace) window.history.replaceState({}, "", to);
  else window.history.pushState({}, "", to);
  emit();
  const targetHash = new URL(to, window.location.href).hash;
  if (targetHash) {
    window.requestAnimationFrame(() => {
      const target = document.getElementById(targetHash.slice(1));
      const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
      target?.scrollIntoView({ behavior, block: "start" });
    });
  } else {
    window.scrollTo(0, 0);
  }
}

export function useRouteLocation(): RouteLocation {
  const [location, setLocation] = useState<RouteLocation>(readLocation);

  useEffect(() => {
    const update = () => setLocation(readLocation());
    listeners.add(update);
    window.addEventListener("popstate", update);
    window.addEventListener("hashchange", update);
    update();
    return () => {
      listeners.delete(update);
      window.removeEventListener("popstate", update);
      window.removeEventListener("hashchange", update);
    };
  }, []);

  return location;
}

export function useQueryParam(key: string): string | null {
  const { search } = useRouteLocation();
  return new URLSearchParams(search).get(key);
}

interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
}

export function Link({ to, children, onClick, ...anchorProps }: LinkProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  };
  return (
    <a {...anchorProps} href={to} onClick={handleClick}>
      {children}
    </a>
  );
}
