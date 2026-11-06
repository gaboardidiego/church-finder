interface GoatCounter {
  count: (vars: { path: string; title?: string; event?: boolean }) => void;
}

declare global {
  interface Window {
    goatcounter?: GoatCounter & { no_onload?: boolean };
  }
}

const countUrl = 'https://church-finder.goatcounter.com/count';

/** Loads GoatCounter (free, cookie-less). */
export function initAnalytics(): void {
  const script = document.createElement('script');
  script.async = true;
  script.dataset.goatcounter = countUrl;
  script.src = '//gc.zgo.at/count.js';
  document.head.appendChild(script);
}

export function trackEvent(name: string): void {
  window.goatcounter?.count({ path: name, title: name, event: true });
}
