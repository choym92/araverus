'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { type ISourceOptions } from '@tsparticles/engine';
import { initParticlesEngine } from '@tsparticles/react';
import { loadSlim } from '@tsparticles/slim';

const Particles = dynamic(
  () => import('@tsparticles/react').then((m) => m.default),
  { ssr: false, loading: () => null }
);

interface ParticleBackgroundProps {
  className?: string;
}

export default function ParticleBackground({ className }: ParticleBackgroundProps) {
  const [init, setInit] = useState(false);

  useEffect(() => {
    // Initialize particles engine once when component mounts.
    // If reusing this component across multiple pages, consider
    // hoisting initParticlesEngine to a higher-level provider.
    initParticlesEngine(async (engine) => {
      await loadSlim(engine);
    }).then(() => {
      setInit(true);
    });
  }, []);

  const particlesLoaded = async () => {
    // Particles loaded successfully
  };

  const options: ISourceOptions = useMemo(
    () => ({
      fullScreen: { enable: false },
      fpsLimit: 60,
      particles: {
        number: {
          value: 120,
          density: { enable: true, width: 800, height: 800 },
        },
        color: { value: '#1A1A1A' },
        shape: { type: 'circle' },
        size: {
          value: { min: 1.5, max: 3 },
        },
        opacity: {
          value: { min: 0.4, max: 0.8 },
        },
        links: {
          enable: true,
          distance: 120,
          color: '#1A1A1A',
          opacity: 0.25,
          width: 0.8,
        },
        move: {
          enable: true,
          speed: 0.8,
          direction: 'none',
          random: true,
          straight: false,
          outModes: { default: 'out' },
        },
      },
      interactivity: {
        events: {
          onHover: { enable: false },
          onClick: { enable: false },
        },
      },
      detectRetina: true,
    }),
    []
  );

  if (!init) {
    return null;
  }

  return (
    <Particles
      id="landing-hero-particles"
      className={className}
      particlesLoaded={particlesLoaded}
      options={options}
    />
  );
}
