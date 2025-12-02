'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { type Container, type ISourceOptions } from '@tsparticles/engine';
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

  const particlesLoaded = async (container?: Container) => {
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
          value: { min: 1, max: 2 },
        },
        opacity: {
          value: { min: 0.2, max: 0.5 },
        },
        links: {
          enable: true,
          distance: 100,
          color: '#1A1A1A',
          opacity: 0.1,
          width: 0.5,
        },
        move: {
          enable: true,
          speed: 0.15,
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
