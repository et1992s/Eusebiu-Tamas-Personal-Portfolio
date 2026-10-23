import { useEffect } from 'react';
import Lenis from 'lenis';

// ── Module-level handle so route-change effects can drive Lenis ──
let lenisInstance = null;
export function getLenisInstance() {
  return lenisInstance;
}

function SmoothScroll() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const lenis = new Lenis({
      duration: 2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      wheelMultiplier: 1.5,
      touchMultiplier: 5,
      syncTouch: false,
      prevent: (node) =>
        node.nodeType === 1 &&
        (node.hasAttribute?.('data-lenis-prevent') ||
          node.classList?.contains('portfolio-about-chat-messages') ||
          node.classList?.contains('portfolio-chat-window')),
    });

    lenisInstance = lenis;

    let rafId;
    const raf = (time) => {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);

    const onAnchorClick = (e) => {
      const link = e.target.closest?.('a[href^="#"]');
      if (!link) return;
      const id = link.getAttribute('href');
      if (!id || id.length < 2) return;
      const target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      lenis.scrollTo(target, { offset: -88 });
    };
    document.addEventListener('click', onAnchorClick);

    return () => {
      cancelAnimationFrame(rafId);
      document.removeEventListener('click', onAnchorClick);
      lenisInstance = null;
      lenis.destroy();
    };
  }, []);

  return null;
}

export default SmoothScroll;