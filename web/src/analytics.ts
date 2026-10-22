interface GoatCounter {
  count: (vars: { path: string; title?: string; event?: boolean }) => void;
}

declare global {
  interface Window {
    goatcounter?: GoatCounter & { no_onload?: boolean };
  }
}

const code = import.meta.env.VITE_GOATCOUNTER_CODE as string | undefined;

/** Loads GoatCounter (free, cookie-less). Does nothing when no site code is configured. */
export function initAnalytics(): void {
  if (!code) return;
  const script = document.createElement('script');
  script.async = true;
  script.dataset.goatcounter = `https://${code}.goatcounter.com/count`;
  script.src = 'https://gc.zgo.at/count.js';
  document.head.appendChild(script);
}

export function trackEvent(name: string): void {
  if (!code) return;
  window.goatcounter?.count({ path: name, title: name, event: true });
}
