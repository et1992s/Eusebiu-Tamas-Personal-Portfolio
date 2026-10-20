import { useEffect, useRef } from 'react';

function MouseLight() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (window.matchMedia('(hover: none)').matches) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // ---------- Tunables ----------
    const TRAIL_LIFETIME = 700; // ms — how long a segment survives
    const MAX_POINTS     = 50;  // trail length ceiling
    const MIN_DISTANCE   = 4;   // px — skip micro-movements

    // ---------- State ----------
    const points = [];
    let prevX = -1000;
    let prevY = -1000;
    let prevTime = 0;

    let isDark = false;
    let rafId  = 0;

    // ---------- Theme detection ----------
    const site = document.querySelector('.portfolio-site');
    const updateTheme = () => {
      isDark = site?.getAttribute('data-theme') === 'dark';
    };
    updateTheme();

    const observer = new MutationObserver(updateTheme);
    if (site) {
      observer.observe(site, {
        attributes: true,
        attributeFilter: ['data-theme'],
      });
    }

    // ---------- Resize / HiDPI ----------
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    // ---------- Mouse move → append a point ----------
    const onMove = (e) => {
      const now = performance.now();
      const x = e.clientX;
      const y = e.clientY;

      const dx = x - prevX;
      const dy = y - prevY;
      const dist = Math.hypot(dx, dy);

      if (dist < MIN_DISTANCE && prevX !== -1000) {
        prevX = x;
        prevY = y;
        return;
      }

      const dt = Math.max(now - prevTime, 1);
      const speed = dist / dt;

      // Perpendicular jitter — the jaggedness that makes it read as lightning
      const angle    = Math.atan2(dy, dx);
      const perp     = angle + Math.PI / 2;
      const jitterM  = Math.min(dist * 0.35, 12);
      const jitter   = (Math.random() - 0.5) * jitterM;

      points.push({
        x: x + Math.cos(perp) * jitter,
        y: y + Math.sin(perp) * jitter,
        time: now,
        speed,
      });

      if (points.length > MAX_POINTS) points.shift();

      prevX = x;
      prevY = y;
      prevTime = now;
    };

    // ---------- Draw helpers ----------
    const drawSegmentPass = (baseRGB, alphaMul, widthMul, now) => {
      for (let i = 1; i < points.length; i++) {
        const p0 = points[i - 1];
        const p1 = points[i];
        const age  = now - p1.time;
        const life = Math.max(0, 1 - age / TRAIL_LIFETIME);
        if (life <= 0) continue;

        const speedBoost = Math.min(p1.speed * 0.5, 1);
        const alpha = life * alphaMul * (0.4 + speedBoost * 0.6);

        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p1.x, p1.y);
        ctx.strokeStyle = `rgba(${baseRGB}, ${alpha})`;
        ctx.lineWidth = 3 * widthMul * life;
        ctx.stroke();
      }
    };

    // ---------- Animation loop ----------
    const draw = () => {
      const now = performance.now();

      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

      // Expire old points
      while (points.length && now - points[0].time > TRAIL_LIFETIME) {
        points.shift();
      }

      if (points.length >= 2) {
        ctx.lineCap  = 'round';
        ctx.lineJoin = 'round';

        const accent = isDark ? '74, 222, 128' : '16, 185, 129';
        const cyan   = isDark ? '34, 211, 238' : '6, 182, 212';

        // Additive glow only reads well on dark — source-over on light
        ctx.globalCompositeOperation = isDark ? 'lighter' : 'source-over';

        // Pass 1 — wide soft halo
        drawSegmentPass(accent, 0.10, 8.0, now);
        // Pass 2 — cyan body
        drawSegmentPass(cyan,   0.35, 2.5, now);
        // Pass 3 — bright emerald core
        drawSegmentPass(accent, 0.85, 0.9, now);
        // Pass 4 — white-hot center
        drawSegmentPass('255, 255, 255', 1.0, 0.35, now);

        ctx.globalCompositeOperation = 'source-over';
      }

      rafId = requestAnimationFrame(draw);
    };

    // ---------- Wire up ----------
    window.addEventListener('mousemove', onMove, { passive: true });
    rafId = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('resize', resize);
      observer.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="portfolio-mouse-lightning"
      aria-hidden="true"
    />
  );
}

export default MouseLight;