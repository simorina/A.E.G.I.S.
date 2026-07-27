import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { motion } from 'framer-motion';
import { X, Box } from 'lucide-react';

interface ThreeCanvasProps {
  onClose?: () => void;
}

export const ThreeCanvas: React.FC<ThreeCanvasProps> = ({ onClose }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [activeCamName] = useState<string>('TACTICAL ISOMETRIC');

  useEffect(() => {
    if (!containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x070a11, 0.05);

    // 2. Camera setup
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(3.8, 2.5, 3.8);
    camera.lookAt(0, 0, 0);

    // 3. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    containerRef.current.appendChild(renderer.domElement);

    // 4. Create Tactical Particle Point Cloud
    const particleCount = 20000;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const amberColor = new THREE.Color(0xf59e0b);
    const emeraldColor = new THREE.Color(0x10b981);

    for (let i = 0; i < particleCount; i++) {
      // Sphere & Grid Distribution
      const radius = 1.5 + Math.random() * 0.4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      const x = radius * Math.sin(phi) * Math.cos(theta);
      const y = radius * Math.sin(phi) * Math.sin(theta);
      const z = radius * Math.cos(phi);

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      const c = Math.random() > 0.15 ? amberColor : emeraldColor;
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 0.025,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
    });

    const pointsMesh = new THREE.Points(geometry, material);
    scene.add(pointsMesh);

    // 5. Grid Helper
    const gridHelper = new THREE.GridHelper(6, 20, 0xf59e0b, 0x1e293b);
    gridHelper.position.y = -1.2;
    scene.add(gridHelper);

    // 6. Animation Loop
    let animationFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      const elapsedTime = clock.getElapsedTime();
      pointsMesh.rotation.y = elapsedTime * 0.15;
      pointsMesh.rotation.x = Math.sin(elapsedTime * 0.1) * 0.1;

      renderer.render(scene, camera);
      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    // Resize handler
    const handleResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      if (containerRef.current && renderer.domElement) {
        containerRef.current.removeChild(renderer.domElement);
      }
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="relative w-full h-full bg-slate-950/90 rounded-2xl border border-amber-500/40 overflow-hidden shadow-2xl backdrop-blur-md"
    >
      <div ref={containerRef} className="w-full h-full z-0" />

      {/* Top Controls Overlay */}
      <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-auto">
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-950/80 border border-amber-500/30 text-amber-400 font-mono text-xs shadow-md">
          <Box className="w-4 h-4 text-amber-400 animate-spin" />
          <span className="font-bold">{activeCamName}</span>
          <span className="text-[10px] text-emerald-400 border-l border-slate-700 pl-2">THREE.JS 3D PARTICLES</span>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-900 border border-slate-700 hover:border-red-500 text-slate-300 hover:text-red-400 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Bottom Telemetry Overlay */}
      <div className="absolute bottom-3 left-3 z-10 px-3 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-[10px] font-mono text-slate-400">
        <span>PARTICLE COUNT: 20,000 · RENDERER: WEBGL2</span>
      </div>
    </motion.div>
  );
};
