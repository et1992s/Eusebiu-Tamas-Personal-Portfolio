
import { useEffect, useRef, useState } from 'react';
import avatarSvg from '../../assets/avatar.svg?raw';

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
  const avatarArtRef = useRef(null);


  useEffect(() => {
    if (active) {
      playZebioSound('bounce');
    }
  }, [active]);

useEffect(() => {
  const svg = avatarArtRef.current?.querySelector('svg');

  if (!svg) return undefined;

  const pupils = svg.querySelectorAll('.eye-tracking-pupil');

  const resetGaze = () => {
    pupils.forEach((pupil) => {
      pupil.setAttribute('transform', 'translate(0 0)');
    });
  };

  if (!active) {
    resetGaze();
    return undefined;
  }

  const handlePointerMove = (event) => {
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;

    const x = clamp((event.clientX - centerX) / 35, -5, 5);
    const y = clamp((event.clientY - centerY) / 45, -4, 4);

    pupils.forEach((pupil) => {
      pupil.setAttribute('transform', `translate(${x} ${y})`);
    });
  };

  window.addEventListener('pointermove', handlePointerMove);

  return () => {
    window.removeEventListener('pointermove', handlePointerMove);
    resetGaze();
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
      <span
        ref={avatarArtRef}
        className="Zebio-avatar-art"
        aria-hidden="true"
        dangerouslySetInnerHTML={{ __html: avatarSvg }}
      />
    </button>
  );
}

export default ZebioAvatar;
