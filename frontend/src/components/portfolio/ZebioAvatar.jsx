
import { useEffect, useRef, useState } from 'react';

const clamp = (value, min, max) =>
  Math.min(max, Math.max(min, value));


let zebioAudioContext;

function playZebioSound(type) {
  try {
    const AudioContextClass =
      window.AudioContext || window.webkitAudioContext;

    if (!AudioContextClass) return;

    zebioAudioContext ??= new AudioContextClass();

    const context = zebioAudioContext;

    const play = () => {
      const now = context.currentTime;
      const oscillator = context.createOscillator();
      const gain = context.createGain();

      if (type === 'bounce') {
        oscillator.type = 'triangle';
        oscillator.frequency.setValueAtTime(520, now);
        oscillator.frequency.exponentialRampToValueAtTime(
          230,
          now + 0.13,
        );
      } else {
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(620, now);
        oscillator.frequency.exponentialRampToValueAtTime(
          920,
          now + 0.07,
        );
      }

      const duration = type === 'bounce' ? 0.16 : 0.11;
      const volume = type === 'bounce' ? 0.045 : 0.035;

      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(volume, now + 0.012);
      gain.gain.exponentialRampToValueAtTime(
        0.0001,
        now + duration,
      );

      oscillator.connect(gain);
      gain.connect(context.destination);

      oscillator.start(now);
      oscillator.stop(now + duration);
    };

    if (context.state === 'suspended') {
      context.resume().then(play).catch(() => {});
    } else {
      play();
    }
  } catch {
    // Audio is optional; it must never break the avatar.
  }
}

function ZebioAvatar({ active = false, onMoodChange }) {
  const [amazed, setAmazed] = useState(false);
  const moodTimeoutRef = useRef(null);
  const [gaze, setGaze] = useState({ x: 0, y: 0 });


  useEffect(() => {
    if (active) {
      playZebioSound('bounce');
    }
  }, [active]);

  useEffect(() => {
    if (!active) {
      setGaze({ x: 0, y: 0 });
      return undefined;
    }

    const handlePointerMove = (event) => {
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;

      setGaze({
        x: clamp((event.clientX - centerX) / 35, -5, 5),
        y: clamp((event.clientY - centerY) / 45, -4, 4),
      });
    };

    window.addEventListener('pointermove', handlePointerMove);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
    };
  }, [active]);



  const toggleMood = () => {
    playZebioSound('click');

    if (moodTimeoutRef.current) {
      window.clearTimeout(moodTimeoutRef.current);
    }

    setAmazed(true);
    onMoodChange?.('amazed');

    moodTimeoutRef.current = window.setTimeout(() => {
      setAmazed(false);
      onMoodChange?.('happy');
      moodTimeoutRef.current = null;
    }, 1000);
  };

  useEffect(() => {
    return () => {
      if (moodTimeoutRef.current) {
        window.clearTimeout(moodTimeoutRef.current);
      }
    };
  }, []);

  return (
    <button
      type="button"
      className={[
        'Zebio-avatar',
        active ? 'Zebio-avatar--active' : '',
        amazed ? 'Zebio-avatar--amazed' : '',
      ].filter(Boolean).join(' ')}
      onClick={toggleMood}
      aria-label={
        amazed
          ? 'Make Zebio happy again'
          : 'Make Zebio amazed'
      }
      title="Click to change Zebio's mood"
      tabIndex={active ? 0 : -1}
      aria-hidden={!active}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 400 450"
        role="img"
        aria-label={amazed ? 'Amazed Zebio' : 'Happy Zebio'}
      >
        <defs>
          <linearGradient
            id="ZebioAvatarGradient"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#2d8d7fa6" />
            <stop offset="50%" stopColor="#118d5793" />
            <stop offset="100%" stopColor="#067e3493" />
          </linearGradient>

          <linearGradient
            id="ZebioAvatarHighlight"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#26796ca6" stopOpacity=".19" />
            <stop offset="50%" stopColor="#0f794b93" stopOpacity=".21" />
            <stop offset="100%" stopColor="#05692b93" stopOpacity=".18" />
          </linearGradient>
        </defs>

        <path
          d="M120 40 L280 40 A55 55 0 0 1 335 95
             L220 210 A10 10 0 0 0 220 225
             L335 340 A55 55 0 0 1 280 395
             L120 395 A55 55 0 0 1 65 340
             L180 225 A10 10 0 0 0 180 210
             L65 95 A55 55 0 0 1 120 40 Z"
          fill="url(#ZebioAvatarGradient)"
          stroke="url(#ZebioAvatarGradient)"
          strokeWidth="46"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <path
          d="M120 40 L280 40 A55 55 0 0 1 335 95
             L220 210 A10 10 0 0 0 220 225
             L335 340 A55 55 0 0 1 280 395
             L120 395 A55 55 0 0 1 65 340
             L180 225 A10 10 0 0 0 180 210
             L65 95 A55 55 0 0 1 120 40 Z"
          fill="none"
          stroke="url(#ZebioAvatarHighlight)"
          strokeWidth="40"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <g
          className="Zebio-avatar-normal-eyes"
          fill="#050505"
          transform={`translate(${gaze.x} ${gaze.y})`}
        >
          <ellipse cx="130" cy="90" rx="12" ry="14">
            <animate
              attributeName="ry"
              dur="5.8s"
              repeatCount="indefinite"
              values="14;14;1.2;14;14;1.2;14"
              keyTimes="0;.12;.145;.17;.50;.525;1"
            />
          </ellipse>

          <ellipse cx="270" cy="90" rx="12" ry="14">
            <animate
              attributeName="ry"
              dur="5.8s"
              repeatCount="indefinite"
              values="14;14;1.2;14;14;1.2;14"
              keyTimes="0;.12;.145;.17;.50;.525;1"
            />
          </ellipse>
        </g>

        <g
          className="Zebio-avatar-happy-eyes"
          fill="none"
          stroke="#050505"
          strokeWidth="9"
          strokeLinecap="round"
          transform={`translate(${gaze.x} ${gaze.y})`}
        >
          <path d="M114 98 Q130 72 146 98" />
          <path d="M254 98 Q270 72 286 98" />
        </g>

        <path
          className="Zebio-avatar-smile"
          d="M160 300 Q200 340 240 300"
          fill="none"
          stroke="#050505"
          strokeWidth="9"
          strokeLinecap="round"
        />

        <circle
          className="Zebio-avatar-wow"
          cx="200"
          cy="303"
          r="25"
          fill="#050505"
        />
      </svg>
    </button>
  );
}

export default ZebioAvatar;
