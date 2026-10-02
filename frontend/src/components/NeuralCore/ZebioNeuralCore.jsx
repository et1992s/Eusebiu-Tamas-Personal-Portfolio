import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/* ==================================================================
   RNG
================================================================== */

function makeRng(seed) {
  let s = seed >>> 0;
  return function rng() {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

/* ==================================================================
   FILAMENT GEOMETRY
   Each filament is a CatmullRom curve from the core outward, with a
   perpendicular bend and a Z wiggle so it snakes like plasma.
================================================================== */

const BURST = {
  MAX_X: 3.6,
  MAX_Y: 1.65,
  MAX_Z: 1.10,
  COUNT: 420,
};

function generateFilaments(count, seed) {
  const rng = makeRng(seed);
  const out = [];

  for (let i = 0; i < count; i += 1) {
    const theta = rng() * Math.PI * 2;
    const rBase = 0.5 + Math.pow(rng(), 0.85) * 0.55;

    const ex = Math.cos(theta) * rBase * BURST.MAX_X;
    const ey = Math.sin(theta) * rBase * BURST.MAX_Y;
    const ez = (rng() - 0.5) * 2 * BURST.MAX_Z;

    const curveBias = (rng() - 0.5) * 2;
    const zBias = (rng() - 0.5) * 2;
    const phase = rng() * Math.PI * 2;

    const points = [
      new THREE.Vector3(
        Math.cos(theta) * 0.04,
        Math.sin(theta) * 0.04,
        0,
      ),
    ];

    const STEPS = 5;
    for (let s = 1; s <= STEPS; s += 1) {
      const t = s / STEPS;
      const tr = Math.pow(t, 0.72);

      let px = ex * tr;
      let py = ey * tr;
      let pz = ez * tr;

      const perpX = -Math.sin(theta);
      const perpY = Math.cos(theta);
      const bendMag =
        curveBias * 0.42 * Math.sin(Math.PI * tr) * BURST.MAX_X;

      px += perpX * bendMag;
      py += perpY * bendMag * 0.55;
      pz += Math.sin(tr * Math.PI * 2 + phase) * 0.22 * tr * zBias;

      points.push(new THREE.Vector3(px, py, pz));
    }

    points[points.length - 1].set(ex, ey, ez);

    const curve = new THREE.CatmullRomCurve3(
      points,
      false,
      'catmullrom',
      0.5,
    );

    const r = rng();
    const tier = r < 0.24 ? 0 : r < 0.74 ? 1 : 2;

    out.push({
      curve,
      endpoint: points[points.length - 1],
      tier,
      brightness: 0.45 + rng() * 0.55,
    });
  }

  return out;
}

const FILAMENTS = generateFilaments(BURST.COUNT, 0x5eed);

/* ==================================================================
   GEOMETRY MERGE
================================================================== */

function mergeGeometries(geoms) {
  let vTotal = 0;
  let iTotal = 0;
  for (const g of geoms) {
    vTotal += g.attributes.position.count;
    iTotal += g.index.count;
  }

  const pos = new Float32Array(vTotal * 3);
  const nor = new Float32Array(vTotal * 3);
  const uv = new Float32Array(vTotal * 2);
  const idx = new Uint32Array(iTotal);

  let v = 0;
  let ii = 0;
  for (const g of geoms) {
    const p = g.attributes.position.array;
    const n = g.attributes.normal.array;
    const u = g.attributes.uv.array;
    const ix = g.index.array;
    const vc = g.attributes.position.count;
    const ic = g.index.count;

    pos.set(p, v * 3);
    nor.set(n, v * 3);
    uv.set(u, v * 2);
    for (let k = 0; k < ic; k += 1) idx[ii + k] = ix[k] + v;

    v += vc;
    ii += ic;
  }

  const merged = new THREE.BufferGeometry();
  merged.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  merged.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  merged.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  merged.setIndex(new THREE.BufferAttribute(idx, 1));
  return merged;
}

function buildTierGeometry(filaments, radius) {
  const geoms = filaments.map(
    (f) => new THREE.TubeGeometry(f.curve, 14, radius, 3, false),
  );
  const merged = mergeGeometries(geoms);
  for (const g of geoms) g.dispose();
  return merged;
}

const GEOM = (() => {
  const byTier = [[], [], []];
  for (const f of FILAMENTS) byTier[f.tier].push(f);

  return {
    dim:    buildTierGeometry(byTier[0], 0.0038),
    mid:    buildTierGeometry(byTier[1], 0.0052),
    bright: buildTierGeometry(byTier[2], 0.0072),
  };
})();

/* ==================================================================
   PALETTES
================================================================== */

const PALETTES = {
  idle: {
    core: '#d8ecf8', corona: '#5b90a8', accent: '#7aaec4',
    signal: '#ffffff', dim: 0.2, flow: 0.01,
  },
  initialising: {
    core: '#d8ecf8', corona: '#5b90a8', accent: '#7aaec4',
    signal: '#ffffff', dim: 0.5, flow: 0.3,
  },
  processing: {
    core: '#d8ecf8', corona: '#5b90a8', accent: '#7aaec4',
    signal: '#ffffff', dim: 0.5, flow: 0.4,
  },
  waiting: {
    core: '#f2e6ff', corona: '#8040c0', accent: '#b088e0',
    signal: '#e8d0ff', dim: 0.5, flow: 0.0,
  },
  complete: {
    core: '#f8ffe0', corona: '#88cc40', accent: '#b0e878',
    signal: '#ffffff', dim: 0.5, flow: 0.0,
  },
  failed: {
    core: '#ffe0e0', corona: '#c04050', accent: '#f09090',
    signal: '#ffe0e0', dim: 0.5, flow: 0.0,
  },
  cancelled: {
    core: '#a0a8b5', corona: '#404850', accent: '#708090',
    signal: '#a0a8b5', dim: 0.5, flow: 0.0,
  },
};

/* ==================================================================
   RADIAL GLOW TEXTURE
================================================================== */

function makeGlowTexture(stops) {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  const g = ctx.createRadialGradient(
    size / 2, size / 2, 0,
    size / 2, size / 2, size / 2,
  );
  for (const [offset, color] of stops) g.addColorStop(offset, color);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  return tex;
}

function GlowSprite({ size, stops, opacity = 1 }) {
  const texture = useMemo(() => makeGlowTexture(stops), [stops]);
  useEffect(() => () => texture.dispose(), [texture]);

  return (
    <mesh>
      <planeGeometry args={[size, size]} />
      <meshBasicMaterial
        map={texture}
        transparent
        opacity={opacity}
        depthWrite={false}
        depthTest={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </mesh>
  );
}

/* ==================================================================
   CORE
================================================================== */

function Core({ palette, active }) {
  const groupRef = useRef();
  const hotRef = useRef();
  const coronaRef = useRef();

  const hotStops = useMemo(
    () => [
      [0, 'rgba(0, 217, 255, 0.76)'],
      [0.15, 'rgba(0, 225, 255, 0.31)', palette.core],
      [0.40, `${palette.corona}05`],
      [1, 'rgba(0, 238, 255, 0)'],
    ],
    [palette.core, palette.corona],
  );

  const coronaStops = useMemo(
    () => [
      [0, 'rgba(0, 255, 242, 0.56)', `${palette.corona}cc`],
      [0.45, 'rgba(0, 204, 255, 0.14)', `${palette.corona}65`],
      [1, 'rgba(0, 252, 239, 0)'],
    ],
    [palette.corona],
  );

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const pulse = active ? 1 + Math.sin(t * 3.4) * 0.07 : 1;
    if (groupRef.current) groupRef.current.scale.setScalar(pulse);
    if (hotRef.current) hotRef.current.rotation.z = t * 0.1;
    if (coronaRef.current) coronaRef.current.rotation.z = -t * 0.2;
  });

  return (
    <group ref={groupRef}>
      <mesh>
        <sphereGeometry args={[0.055, 16, 16]} />
        <meshBasicMaterial color="#03f5fd77" toneMapped={false} />
      </mesh>

      <group ref={hotRef}>
        <GlowSprite size={8.6} stops={hotStops} opacity={0.1} />
      </group>

      <group ref={coronaRef}>
        <GlowSprite size={6.6} stops={coronaStops} opacity={0.1} />
      </group>
    </group>
  );
}

/* ==================================================================
   FILAMENT LAYER — one merged tube per tier
================================================================== */

function FilamentLayer({ geometry, color, opacity }) {
  return (
    <mesh geometry={geometry} frustumCulled={false}>
      <meshBasicMaterial
        color={color}
        transparent
        opacity={opacity}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </mesh>
  );
}

/* ==================================================================
   ENDPOINT NODES — twinkling instanced dots
================================================================== */

function Endpoints({ color, dim }) {
  const ref = useRef();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const count = FILAMENTS.length;

  const baseSize = useMemo(
    () => FILAMENTS.map((f) => 0.022 + f.brightness * 0.018),
    [],
  );

  useFrame(({ clock }) => {
    const mesh = ref.current;
    if (!mesh) return;
    const t = clock.elapsedTime;

    for (let i = 0; i < count; i += 1) {
      const f = FILAMENTS[i];
      const phase = i * 0.9;
      const twinkle = 0.42 + 0.38 * Math.sin(t * 1.85 + phase);

      dummy.position.set(
        f.endpoint.x,
        f.endpoint.y,
        f.endpoint.z,
      );
      dummy.scale.setScalar(baseSize[i] * twinkle);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={ref}
      args={[null, null, count]}
      frustumCulled={false}
    >
      <sphereGeometry args={[1, 5, 5]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={1 * dim}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

/* ==================================================================
   SIGNALS
   White light travelling core → tip. Only emitted while the agent
   is running. A single heartbeat rhythm: outward travel for the
   first 60% of the cycle, then a quiet gap before the next wave.
================================================================== */

const SIGNAL_FILAMENTS = (() => {
  const rng = makeRng(0xc0ffee);
  return FILAMENTS.filter(() => rng() < 0.95);
})();

function Signals({ speed, dim }) {
  const ref = useRef();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const count = SIGNAL_FILAMENTS.length;

  useFrame(({ clock }) => {
    const mesh = ref.current;
    if (!mesh || speed <= 0) return;

    const t = clock.elapsedTime;

    for (let i = 0; i < count; i += 1) {
      const f = SIGNAL_FILAMENTS[i];

      // Stagger slightly so it feels like a wave, not a strobe
      const cycle = (t * speed * 0.15 + i * 0.004) % 1;

      // Head travels outward during the first 60% of the cycle
      const phase = Math.min(cycle / 0.6, 1);

      const p = f.curve.getPoint(phase);
      dummy.position.copy(p);

      // Bright near the core, fading toward the tip
      const fade = 0.8 - phase * 0.9;
      dummy.scale.setScalar(fade);

      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  });

  if (speed <= 0) return null;

  return (
    <instancedMesh
      ref={ref}
      args={[null, null, count]}
      frustumCulled={false}
    >
      <sphereGeometry args={[0.025, 5, 5]} />
      <meshBasicMaterial
        color="#ffffff"
        transparent
        opacity={0.95 * dim}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

/* ==================================================================
   BURST — the whole scene, gently rotating
================================================================== */

function Burst({ palette, active, reducedMotion }) {
  const ref = useRef();

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.elapsedTime;

    if (reducedMotion) {
      ref.current.rotation.y = 0.01;
      ref.current.rotation.x = 0.01;
      return;
    }

    ref.current.rotation.y = Math.sin(t * 0.46) * 0.68;
    ref.current.rotation.x = Math.sin(t * 0.16) * 0.08;
  });

  const d = palette.dim;

  return (
    <group ref={ref}>
      <FilamentLayer
        geometry={GEOM.dim}
        color={palette.accent}
        opacity={0.22 * d}
      />
      <FilamentLayer
        geometry={GEOM.mid}
        color={palette.accent}
        opacity={0.48 * d}
      />
      <FilamentLayer
        geometry={GEOM.bright}
        color={palette.accent}
        opacity={0.95 * d}
      />

      <Endpoints color={palette.accent} dim={d} />

      <Signals
        speed={active ? palette.flow : 0}
        dim={d}
      />

      <Core palette={palette} active={active} />
    </group>
  );
}

/* ==================================================================
   SCENE
================================================================== */

function NeuralScene({ palette, visualState, reducedMotion }) {
  // Pulse ONLY while the agent is running.
  const active = visualState === 'processing';

  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 45 }}
      dpr={[1, 2]}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance',
      }}
      style={{ background: 'transparent' }}
    >
      <Burst
        palette={palette}
        active={active}
        reducedMotion={reducedMotion}
      />
    </Canvas>
  );
}

/* ==================================================================
   MAIN
================================================================== */

function ZebioNeuralCore({
  taskState,
  taskError,
  onApprove,
  onReject,
}) {
  const steps = useMemo(
    () => taskState?.steps ?? [],
    [taskState],
  );

  const visualState = useMemo(() => {
    if (!taskState) return 'idle';
    if (steps.some((s) => s.approval_status === 'pending')) {
      return 'waiting';
    }
    switch (taskState.status) {
      case 'pending':   return 'initialising';
      case 'running':   return 'processing';
      case 'completed': return 'complete';
      case 'failed':    return 'failed';
      case 'cancelled': return 'cancelled';
      default:          return 'idle';
    }
  }, [taskState, steps]);

  const palette = PALETTES[visualState] ?? PALETTES.idle;

  const pendingApproval = useMemo(
    () =>
      steps.find(
        (s) =>
          s.approval_id && s.approval_status === 'pending',
      ) ?? null,
    [steps],
  );

  const thought = useMemo(() => {
    if (!taskState) return 'Awaiting your command';
    if (taskState.status === 'completed') return 'Task completed successfully';
    if (taskState.status === 'failed')    return 'Task execution failed';
    if (taskState.status === 'cancelled') return 'Task was cancelled';
    if (pendingApproval) {
      return `Awaiting approval to run ${pendingApproval.tool_name}`;
    }
    return (
      taskState.current_thought ||
      taskState.current_output ||
      taskState.current_step ||
      taskState.message ||
      (taskState.status === 'pending'
        ? 'Initialising engineering task'
        : 'Reasoning through the next step')
    );
  }, [taskState, pendingApproval]);

  const [thoughtHead, thoughtTail] = useMemo(() => {
    const words = String(thought).trim().split(/\s+/);
    const HEAD = 6;
    if (words.length <= HEAD) return [words.join(' '), ''];
    return [
      words.slice(0, HEAD).join(' '),
      words.slice(HEAD).join(' '),
    ];
  }, [thought]);

  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return undefined;
    }
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(mq.matches);
    update();
    mq.addEventListener?.('change', update);
    return () => mq.removeEventListener?.('change', update);
  }, []);

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <section
      className={`zebio-neural-core zebio-neural-core-${visualState}`}
      aria-live="polite"
      aria-label="Zebio engineering activity"
      style={{
        '--core-accent': palette.accent,
        '--core-glow': `${palette.corona}33`,
        '--core-dim': palette.dim,
      }}
    >
      <div className="zebio-thought" aria-live="polite">
        <span className="zebio-thought-dots" aria-hidden="true">
          <i /><i /><i />
        </span>
        <span className="zebio-thought-text">
          <span className="zebio-thought-head">{thoughtHead}</span>
          {thoughtTail && (
            <span className="zebio-thought-tail"> {thoughtTail}</span>
          )}
        </span>
      </div>

      <div className="zebio-neural-stage" aria-hidden="true">
        <div className="zebio-neural-glow" />
        <div className="zebio-neural-canvas-wrap">
          {mounted && (
            <NeuralScene
              palette={palette}
              visualState={visualState}
              reducedMotion={reducedMotion}
            />
          )}
        </div>
        <div className="zebio-neural-vignette" />
      </div>

      {taskState && (
        <div className="zebio-neural-task">
          {pendingApproval && (
            <div className="zebio-neural-approval">
              <div className="zebio-neural-approval-tool">
                {pendingApproval.tool_name}
              </div>
              <div className="zebio-neural-approval-actions">
                <button
                  type="button"
                  onClick={() =>
                    onApprove?.(pendingApproval.approval_id)
                  }
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() =>
                    onReject?.(pendingApproval.approval_id)
                  }
                >
                  Reject
                </button>
              </div>
            </div>
          )}

          {taskError && (
            <div className="zebio-neural-error">{taskError}</div>
          )}
        </div>
      )}
    </section>
  );
}

export default ZebioNeuralCore;