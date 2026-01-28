'use client';

import { useRef, useEffect } from 'react';
import * as THREE from 'three';

interface WaveGridProps {
  className?: string;
}

export default function WaveGrid({ className }: WaveGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    let width = container.clientWidth || window.innerWidth;
    let height = container.clientHeight || window.innerHeight;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(0, 5, 30); // Front view for infinity sign
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Infinity sign with uniform point distribution
    const numPoints = 2500;

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(numPoints * 3);

    // Pre-generate random offsets for each point (consistent across frames)
    const randomOffsets: { t: number; r: number; angle: number }[] = [];
    for (let i = 0; i < numPoints; i++) {
      randomOffsets.push({
        t: Math.random() * Math.PI * 2, // Position along curve
        r: Math.random() * 2.5, // Distance from curve center
        angle: Math.random() * Math.PI * 2, // Angle around curve
      });
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    // Material - blue dots
    const material = new THREE.PointsMaterial({
      color: 0x4A90E2,
      size: 0.15,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.9,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // Mouse tracking - calculate frustum dimensions for accurate mapping
    const mouse3D = { x: 9999, y: 9999 };
    const fov = 60;
    const cameraZ = 30;
    // Calculate visible height at z=0: 2 * distance * tan(fov/2)
    const visibleHeight = 2 * cameraZ * Math.tan((fov * Math.PI) / 360);

    const handleMouseMove = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const aspect = rect.width / rect.height;
      const visibleWidth = visibleHeight * aspect;
      // Map mouse to world coordinates using camera frustum
      const mouseX = ((event.clientX - rect.left) / rect.width - 0.5) * visibleWidth;
      const mouseY = -((event.clientY - rect.top) / rect.height - 0.5) * visibleHeight;
      mouse3D.x = mouseX;
      mouse3D.y = mouseY;
    };

    const handleMouseLeave = () => {
      mouse3D.x = 9999;
      mouse3D.y = 9999;
    };

    container.addEventListener('mousemove', handleMouseMove);
    container.addEventListener('mouseleave', handleMouseLeave);

    // Animation
    let time = 0;

    const animate = () => {
      time += 0.008; // Slower, elegant animation

      const posArray = geometry.attributes.position.array as Float32Array;
      let index = 0;

      // Infinity sign with randomized uniform distribution
      for (let i = 0; i < numPoints; i++) {
        const offset = randomOffsets[i];
        const t = offset.t;

        // Organic breathing
        const breathe = 1 + Math.sin(time * 0.4) * 0.1;
        const scale = 15 * breathe;

        // Lemniscate parametric equations (base curve)
        const denom = 1 + Math.sin(t) * Math.sin(t);
        const baseX = scale * Math.cos(t) / denom;
        const baseY = scale * Math.sin(t) * Math.cos(t) / denom;

        // Random offset around the curve (tube-like distribution)
        const animatedAngle = offset.angle + time * 0.3;
        const offsetX = offset.r * Math.cos(animatedAngle);
        const offsetY = offset.r * Math.sin(animatedAngle) * 0.5;
        const offsetZ = offset.r * Math.sin(animatedAngle);

        // Subtle flowing wave
        const wave = Math.sin(t * 3 + time * 1.5) * 0.5;

        let finalX = baseX + offsetX;
        let finalY = baseY + offsetY + wave;
        let finalZ = offsetZ;

        // Mouse Repulsion + Depth Push
        const dx = finalX - mouse3D.x;
        const dy = finalY - mouse3D.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const maxDist = 3; // Effect radius (smaller)

        if (dist < maxDist && dist > 0.1) {
          const force = Math.pow(1 - dist / maxDist, 2); // Smooth falloff
          const repelStrength = 3; // Repulsion strength (reduced)
          const depthStrength = 4; // Depth push strength (reduced)

          // Repulsion - push away in XY
          finalX += (dx / dist) * force * repelStrength;
          finalY += (dy / dist) * force * repelStrength;

          // Depth Push - push forward in Z
          finalZ += force * depthStrength;
        }

        posArray[index] = finalX;
        posArray[index + 1] = finalY;
        posArray[index + 2] = finalZ;
        index += 3;
      }

      geometry.attributes.position.needsUpdate = true;

      // Gentle auto rotation - subtle tilt for infinity sign
      points.rotation.x = Math.sin(time * 0.2) * 0.15;
      points.rotation.z = Math.sin(time * 0.15) * 0.1;

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    };

    animate();

    // Resize handler
    const handleResize = () => {
      width = container.clientWidth || window.innerWidth;
      height = container.clientHeight || window.innerHeight;

      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      container.removeEventListener('mousemove', handleMouseMove);
      container.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('resize', handleResize);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, []);

  return <div ref={containerRef} className={className} style={{ width: '100%', height: '100%' }} />;
}
