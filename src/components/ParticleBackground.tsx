'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { type ISourceOptions } from '@tsparticles/engine';
import { initParticlesEngine } from '@tsparticles/react';
import { loadSlim } from '@tsparticles/slim';
import { loadPolygonMaskPlugin } from '@tsparticles/plugin-polygon-mask';

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
      await loadPolygonMaskPlugin(engine);
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
      polygon: {
        enable: true,
        url: '/logo.svg',
        type: 'inline',
        scale: 0.5,
        position: { x: 65, y: 50 },
        inline: {
          arrangement: 'equidistant',
        },
        move: {
          radius: 5,
          type: 'radius',
        },
        draw: {
          enable: false,
        },
      },
      particles: {
        number: {
          value: 100,
        },
        color: { value: '#1A1A1A' },
        shape: { type: 'circle' },
        size: {
          value: { min: 1, max: 2 },
        },
        opacity: {
          value: { min: 0.5, max: 0.9 },
        },
        links: {
          enable: true,
          distance: 30,
          color: '#1A1A1A',
          opacity: 0.15,
          width: 0.5,
        },
        move: {
          enable: true,
          speed: 0.3,
          direction: 'none',
          random: false,
          straight: false,
          outModes: { default: 'bounce' },
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
