import { useEffect, useRef } from 'react';

function useScrollReveal(options = {}) {
  const elementRef = useRef(null);

  useEffect(() => {
    const element = elementRef.current;

    if (!element) {
      return;
    }

    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches;

    if (prefersReducedMotion) {
      element.classList.add('is-revealed');
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          element.classList.add('is-revealed');
        } else {
          element.classList.remove('is-revealed');
        }
      },
      {
        threshold: 0.12,
        rootMargin: '0px 0px -40px 0px',
        ...options,
      },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [options]);

  return elementRef;
}

export default useScrollReveal;
