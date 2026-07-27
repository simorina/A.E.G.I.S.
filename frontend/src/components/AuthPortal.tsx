import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshSurfaceSampler } from 'three/examples/jsm/math/MeshSurfaceSampler.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { apiFetch } from '../utils/api';
import type { User as UserType } from '../types';

interface AuthPortalProps {
  onLoginSuccess: (user: UserType) => void;
}

// Camera Presets from 3dmodels.js
const CAMERA_PRESETS = [
  { id: 'CAM_01', desc: 'TACTICAL ISOMETRIC OVERVIEW', pos: new THREE.Vector3(3.8, 2.5, 3.8), target: new THREE.Vector3(0, 0, 0), speed: 0.4 },
  { id: 'CAM_02', desc: 'LOW-ALTITUDE HERO FLYBY', pos: new THREE.Vector3(2.6, -0.6, 2.6), target: new THREE.Vector3(0, 0.3, 0), speed: 0.6 },
  { id: 'CAM_03', desc: 'SATELLITE TOP-DOWN SCAN', pos: new THREE.Vector3(0.1, 5.5, 0.4), target: new THREE.Vector3(0, 0, 0), speed: 0.2 },
  { id: 'CAM_04', desc: 'STEALTH COCKPIT MACRO INCLINE', pos: new THREE.Vector3(1.6, 0.6, 1.4), target: new THREE.Vector3(-0.2, 0.1, 0), speed: 0.3 },
  { id: 'CAM_05', desc: 'WINGSPAN AERODYNAMIC PROFILING', pos: new THREE.Vector3(-3.4, 1.4, 1.8), target: new THREE.Vector3(0.2, -0.2, 0), speed: 0.5 },
];

const PARTICLE_COUNT = 30000;
const MODEL_NAMES = ['b2/scene.gltf', 'jet/scene.gltf'];
const FOLDER_PATH = '/models/';

export const AuthPortal: React.FC<AuthPortalProps> = ({ onLoginSuccess }) => {
  const canvasContainerRef = useRef<HTMLDivElement | null>(null);
  const titleRef = useRef<HTMLHeadingElement | null>(null);

  const [memAddr, setMemAddr] = useState<string>('0x4F2A');
  const [operatorId, setOperatorId] = useState<string>('OP_ADMIN');
  const [accessKey, setAccessKey] = useState<string>('aegis2026');
  const [btnText, setBtnText] = useState<string>('Initialize_Session');
  const [btnState, setBtnState] = useState<'idle' | 'loading' | 'success' | 'denied'>('idle');
  const [statusText, setStatusText] = useState<string>('WAITING FOR AUTH');

  // HUD Camera Metrics
  const [camPresetId, setCamPresetId] = useState<string>('CAM_01');
  const [camDesc, setCamDesc] = useState<string>('TACTICAL ISOMETRIC OVERVIEW');
  const [camElev, setCamElev] = useState<string>('25.4°');
  const [camAzim, setCamAzim] = useState<string>('142.1°');
  const [camZoom, setCamZoom] = useState<string>('1.0x');

  // Glitch TextScramble effect
  useEffect(() => {
    if (!titleRef.current) return;
    const el = titleRef.current;
    const chars = '!<>-_\\/[]{}—=+*^?#________';
    const targetText = 'INTEL_CORE_v8.4';
    let frame = 0;
    let animId: number;

    const queue: { from: string; to: string; start: number; end: number; char?: string }[] = [];
    for (let i = 0; i < targetText.length; i++) {
      const start = Math.floor(Math.random() * 20);
      const end = start + Math.floor(Math.random() * 20);
      queue.push({ from: '', to: targetText[i], start, end });
    }

    const update = () => {
      let output = '';
      let complete = 0;
      for (let i = 0; i < queue.length; i++) {
        let { to, start, end, char } = queue[i];
        if (frame >= end) {
          complete++;
          output += to;
        } else if (frame >= start) {
          if (!char || Math.random() < 0.28) {
            char = chars[Math.floor(Math.random() * chars.length)];
            queue[i].char = char;
          }
          output += `<span style="opacity: 0.5">${char}</span>`;
        } else {
          output += '';
        }
      }
      el.innerHTML = output;
      if (complete < queue.length) {
        frame++;
        animId = requestAnimationFrame(update);
      }
    };

    update();
    return () => cancelAnimationFrame(animId);
  }, []);

  // Random Memory Address Generator
  useEffect(() => {
    const timer = setInterval(() => {
      setMemAddr('0x' + Math.floor(Math.random() * 16777215).toString(16).toUpperCase().substring(0, 4));
    }, 150);
    return () => clearInterval(timer);
  }, []);

  // Three.js 3D GLTF Model Morphing
  useEffect(() => {
    if (!canvasContainerRef.current) return;
    const container = canvasContainerRef.current;
    const width = container.clientWidth || window.innerWidth - 350;
    const height = container.clientHeight || window.innerHeight;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x050505, 0.05);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.copy(CAMERA_PRESETS[0].pos);
    camera.lookAt(CAMERA_PRESETS[0].target);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = true;
    controls.autoRotateSpeed = CAMERA_PRESETS[0].speed;

    const modelPositions: Float32Array[] = [];
    let currentModelIdx = 0;
    let points: THREE.Points | null = null;

    function calculateSurfaceArea(mesh: THREE.Mesh): number {
      if (!mesh || !mesh.geometry || !mesh.geometry.attributes || !mesh.geometry.attributes.position) return 0.01;
      const geometry = mesh.geometry;
      const position = geometry.attributes.position;
      if (position.count < 3) return 0.01;

      const index = geometry.index;
      let area = 0;
      const pA = new THREE.Vector3(), pB = new THREE.Vector3(), pC = new THREE.Vector3();
      const ab = new THREE.Vector3(), ac = new THREE.Vector3(), cross = new THREE.Vector3();

      try {
        if (index) {
          for (let i = 0; i < index.count; i += 3) {
            pA.fromBufferAttribute(position, index.getX(i));
            pB.fromBufferAttribute(position, index.getX(i + 1));
            pC.fromBufferAttribute(position, index.getX(i + 2));

            ab.subVectors(pB, pA);
            ac.subVectors(pC, pA);
            cross.crossVectors(ab, ac);
            area += cross.length() * 0.5;
          }
        } else {
          for (let i = 0; i < position.count; i += 3) {
            pA.fromBufferAttribute(position, i);
            pB.fromBufferAttribute(position, i + 1);
            pC.fromBufferAttribute(position, i + 2);

            ab.subVectors(pB, pA);
            ac.subVectors(pC, pA);
            cross.crossVectors(ab, ac);
            area += cross.length() * 0.5;
          }
        }
      } catch {
        return 0.01;
      }

      const scale = mesh.getWorldScale(new THREE.Vector3());
      const scaleFactor = Math.abs(scale.x * scale.y);
      area *= (scaleFactor > 0 ? scaleFactor : 1);
      return isNaN(area) || area <= 0 ? 0.01 : area;
    }

    function sampleAndNormalize(model: THREE.Object3D, targetArray: Float32Array) {
      let meshEntries: { mesh: THREE.Mesh; area: number }[] = [];
      let totalArea = 0;

      model.updateMatrixWorld(true);
      model.traverse((n) => {
        const mesh = n as THREE.Mesh;
        if (mesh.isMesh && mesh.geometry && mesh.geometry.attributes && mesh.geometry.attributes.position) {
          const area = calculateSurfaceArea(mesh);
          meshEntries.push({ mesh, area });
          totalArea += area;
        }
      });

      if (meshEntries.length === 0) return;

      const box = new THREE.Box3().setFromObject(model);
      const size = new THREE.Vector3();
      box.getSize(size);
      const center = new THREE.Vector3();
      box.getCenter(center);

      const maxDim = Math.max(size.x, size.y, size.z);
      const scaleFactor = 4.5 / (maxDim || 1);

      let arrayIndex = 0;
      const _v = new THREE.Vector3();
      const minParticlesPerMesh = Math.max(30, Math.floor((PARTICLE_COUNT * 0.25) / meshEntries.length));
      const proportionalBudget = PARTICLE_COUNT - (minParticlesPerMesh * meshEntries.length);

      meshEntries.forEach((entry) => {
        const mesh = entry.mesh;
        const meshArea = entry.area;
        let numParticles = minParticlesPerMesh + Math.floor((meshArea / (totalArea || 1)) * proportionalBudget);
        if (numParticles < 1) numParticles = 1;

        try {
          const sampler = new MeshSurfaceSampler(mesh).build();
          for (let i = 0; i < numParticles; i++) {
            if (arrayIndex >= PARTICLE_COUNT * 3) break;
            sampler.sample(_v);
            _v.applyMatrix4(mesh.matrixWorld);

            targetArray[arrayIndex] = (_v.x - center.x) * scaleFactor;
            targetArray[arrayIndex + 1] = (_v.y - center.y) * scaleFactor;
            targetArray[arrayIndex + 2] = (_v.z - center.z) * scaleFactor;
            arrayIndex += 3;
          }
        } catch {
          const posAttr = mesh.geometry.attributes.position;
          for (let i = 0; i < numParticles; i++) {
            if (arrayIndex >= PARTICLE_COUNT * 3) break;
            const vIdx = Math.floor((i / numParticles) * posAttr.count) % posAttr.count;
            _v.fromBufferAttribute(posAttr, vIdx);
            _v.applyMatrix4(mesh.matrixWorld);

            targetArray[arrayIndex] = (_v.x - center.x) * scaleFactor;
            targetArray[arrayIndex + 1] = (_v.y - center.y) * scaleFactor;
            targetArray[arrayIndex + 2] = (_v.z - center.z) * scaleFactor;
            arrayIndex += 3;
          }
        }
      });

      while (arrayIndex < PARTICLE_COUNT * 3) {
        targetArray[arrayIndex] = targetArray[arrayIndex - 3] || 0;
        targetArray[arrayIndex + 1] = targetArray[arrayIndex - 2] || 0;
        targetArray[arrayIndex + 2] = targetArray[arrayIndex - 1] || 0;
        arrayIndex += 3;
      }
    }

    function createPoints(initialPosArray: Float32Array) {
      const geo = new THREE.BufferGeometry();
      // Clone array so we can perform per-frame morphing LERP
      const currentPosArray = new Float32Array(initialPosArray);
      geo.setAttribute('position', new THREE.BufferAttribute(currentPosArray, 3));

      const mat = new THREE.PointsMaterial({
        color: new THREE.Color("rgb(245, 158, 11)"),
        size: 0.015,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending,
      });

      points = new THREE.Points(geo, mat);
      scene.add(points);
    }

    // Load GLTF 3D Models
    const loader = new GLTFLoader();
    const loadGLTFModels = async () => {
      try {
        for (const name of MODEL_NAMES) {
          const gltf = await loader.loadAsync(FOLDER_PATH + name);
          const posArray = new Float32Array(PARTICLE_COUNT * 3);
          sampleAndNormalize(gltf.scene, posArray);
          modelPositions.push(posArray);
        }

        if (modelPositions.length > 0) {
          createPoints(modelPositions[0]);
        }
      } catch (err) {
        console.warn("GLTF Load fallback to sphere:", err);
        const sphereGeo = new THREE.SphereGeometry(1.5, 128, 128);
        const posArray = new Float32Array(PARTICLE_COUNT * 3);
        const sampler = new MeshSurfaceSampler(new THREE.Mesh(sphereGeo)).build();
        const _v = new THREE.Vector3();
        for (let i = 0; i < PARTICLE_COUNT; i++) {
          sampler.sample(_v);
          posArray[i * 3] = _v.x * 1.5;
          posArray[i * 3 + 1] = _v.y * 1.5;
          posArray[i * 3 + 2] = _v.z * 1.5;
        }
        modelPositions.push(posArray);
        createPoints(posArray);
      }
    };

    loadGLTFModels();

    // Camera Cycle Timer
    let activeCamIdx = 0;
    let targetCamPos = new THREE.Vector3().copy(CAMERA_PRESETS[0].pos);
    let targetCamLook = new THREE.Vector3().copy(CAMERA_PRESETS[0].target);

    const camCycleTimer = setInterval(() => {
      activeCamIdx = (activeCamIdx + 1) % CAMERA_PRESETS.length;
      const preset = CAMERA_PRESETS[activeCamIdx];
      targetCamPos.copy(preset.pos);
      targetCamLook.copy(preset.target);
      controls.autoRotateSpeed = preset.speed;
      setCamPresetId(preset.id);
      setCamDesc(preset.desc);
    }, 7000);

    // Morphing timer switching current target index every 6 seconds
    const morphTimer = setInterval(() => {
      if (modelPositions.length > 1) {
        currentModelIdx = (currentModelIdx + 1) % modelPositions.length;
      }
    }, 6000);

    // Animation Loop with Per-Frame Particle Morphing LERP
    let animId: number;
    const animate = () => {
      // 1. Particle Morphing LERP
      if (points && modelPositions.length > 0) {
        const positions = points.geometry.attributes.position.array as Float32Array;
        const targetSet = modelPositions[currentModelIdx];

        if (targetSet) {
          for (let i = 0; i < PARTICLE_COUNT * 3; i++) {
            positions[i] += (targetSet[i] - positions[i]) * 0.03;
          }
          points.geometry.attributes.position.needsUpdate = true;
        }
      }

      // 2. Smooth Camera Drift & Interpolation
      camera.position.lerp(targetCamPos, 0.03);
      controls.target.lerp(targetCamLook, 0.03);
      controls.update();

      // 3. Update Camera HUD Metrics
      const spherical = new THREE.Spherical().setFromVector3(camera.position);
      setCamElev(`${(spherical.phi * (180 / Math.PI)).toFixed(1)}°`);
      setCamAzim(`${(spherical.theta * (180 / Math.PI)).toFixed(1)}°`);
      setCamZoom(`${(3.8 / camera.position.length()).toFixed(1)}x`);

      renderer.render(scene, camera);
      animId = requestAnimationFrame(animate);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      clearInterval(camCycleTimer);
      clearInterval(morphTimer);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      if (points) {
        points.geometry.dispose();
        (points.material as THREE.Material).dispose();
      }
      renderer.dispose();
    };
  }, []);

  // Form Submit Handler matching index.html logic
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setBtnState('loading');
    setBtnText('VERIFYING CREDENTIALS...');

    try {
      const response = await apiFetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operator_id: operatorId,
          access_key: accessKey,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setBtnState('success');
        setBtnText(`ACCESS GRANTED // LEVEL ${data.clearance || 'SIGMA-7'}`);
        setStatusText('ENCRYPTED TUNNEL OPEN');

        const userData: UserType = {
          username: operatorId,
          clearance: data.clearance || 'SIGMA-7',
          token: data.token || 'SESSION_ACTIVE',
        };

        setTimeout(() => {
          sessionStorage.setItem('aegis_auth_user', JSON.stringify(userData));
          localStorage.removeItem('aegis_auth_user');
          onLoginSuccess(userData);
        }, 1200);
      } else {
        throw new Error('Unauthorized');
      }
    } catch {
      setBtnState('denied');
      setBtnText('ACCESS DENIED // INVALID KEY');

      setTimeout(() => {
        setBtnText('Initialize_Session');
        setBtnState('idle');
      }, 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex h-screen w-screen bg-[#050505] text-[#f59e0b] font-mono overflow-hidden select-none">
      {/* CRT Vignette & Scanline Overlays */}
      <div 
        className="pointer-events-none fixed inset-0 z-[999]"
        style={{
          background: 'linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06))',
          backgroundSize: '100% 2px, 3px 100%',
        }}
      />
      <div 
        className="pointer-events-none fixed inset-0 z-[998]"
        style={{
          background: 'radial-gradient(circle, rgba(0,0,0,0) 60%, rgba(0,0,0,0.85) 100%)',
        }}
      />

      {/* Left Panel: Tactical Login Form */}
      <section className="w-[360px] h-full border-r border-[#f59e0b]/20 flex flex-col justify-center p-8 bg-[#0a0a0a]/90 backdrop-blur-md z-[100] shadow-[10px_0_50px_rgba(0,0,0,0.8)] relative shrink-0">
        <div className="mb-10 border-l-4 border-[#f59e0b] pl-3.5">
          <h1 ref={titleRef} className="text-xl font-bold tracking-widest text-[#f59e0b] uppercase shadow-[#f59e0b]/50 drop-shadow-md">
            INTEL_CORE_v8.4
          </h1>
          <div className="text-[10px] tracking-[3px] opacity-80 mt-1">
            AUTHORIZED PERSONNEL ONLY // CLASS_A
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="block text-[10px] uppercase tracking-wider text-[#f59e0b]">
              Operator_ID
            </label>
            <input
              type="text"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="CMD_USR_XXXX"
              required
              className="w-full bg-black/40 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] p-3 text-amber-400 font-mono text-sm outline-none focus:border-[#f59e0b] focus:bg-[#f59e0b]/10 focus:shadow-[0_0_15px_rgba(245,158,11,0.2)] transition-all"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-[10px] uppercase tracking-wider text-[#f59e0b]">
              Access_Key
            </label>
            <input
              type="password"
              value={accessKey}
              onChange={(e) => setAccessKey(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full bg-black/40 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] p-3 text-amber-400 font-mono text-sm outline-none focus:border-[#f59e0b] focus:bg-[#f59e0b]/10 focus:shadow-[0_0_15px_rgba(245,158,11,0.2)] transition-all"
            />
          </div>

          <button
            type="submit"
            disabled={btnState === 'loading'}
            style={{
              backgroundColor: btnState === 'success' ? '#4ade80' : 'transparent',
              color: btnState === 'success' ? '#000' : btnState === 'denied' ? '#ef4444' : '#f59e0b',
              borderColor: btnState === 'success' ? '#4ade80' : btnState === 'denied' ? '#ef4444' : '#f59e0b',
              boxShadow: btnState === 'success' ? '0 0 20px #4ade80' : btnState === 'denied' ? '0 0 15px #ef4444' : 'none',
            }}
            className="w-full py-3.5 px-4 font-bold border transition-all uppercase tracking-[4px] mt-2 font-mono text-xs cursor-pointer hover:bg-[#f59e0b] hover:text-black hover:shadow-[0_0_20px_#f59e0b]"
          >
            {btnText}
          </button>
        </form>

        <div className="mt-auto pt-6 border-t border-[#f59e0b]/20 text-[10px] leading-relaxed opacity-80">
          &gt; CONNECTION: <span className="text-white">SECURE</span><br />
          &gt; ENCRYPTION: AES-256-GCM<br />
          &gt; UPLINK_STATUS:{' '}
          <span className="animate-pulse font-bold" style={{ color: btnState === 'success' ? '#4ade80' : '#f59e0b' }}>
            {statusText}
          </span><br />
          &gt; MEMORY_ADDR: <span className="text-amber-300">{memAddr}</span><br />
          &gt; MANUAL_CTRL: ACTIVE
        </div>
      </section>

      {/* Decorative Lines */}
      <div className="absolute top-10 right-10 w-48 h-[1px] bg-[#f59e0b]/30 pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-24 h-[1px] bg-[#f59e0b]/30 pointer-events-none" />

      {/* Right Panel: Three.js 3D Morphogenesis Canvas & Tactical HUD */}
      <div ref={canvasContainerRef} className="flex-1 h-full relative z-10">
        {/* Tactical HUD Corners Overlay */}
        <div className="absolute inset-6 pointer-events-none z-20">
          <div className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 border-[#f59e0b] opacity-60" />
          <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 border-[#f59e0b] opacity-60" />
          <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 border-[#f59e0b] opacity-60" />
          <div className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 border-[#f59e0b] opacity-60" />

          {/* Camera Info HUD Overlay */}
          <div className="absolute top-4 right-4 bg-[#050505]/85 border border-[#f59e0b]/30 border-r-4 border-r-[#f59e0b] p-3 text-[11px] font-mono tracking-wider shadow-2xl pointer-events-auto backdrop-blur-sm">
            <div className="font-bold text-[#f59e0b] mb-1">
              OPTICAL_CAM // <span>{camPresetId}</span>
            </div>
            <div className="text-white text-xs font-semibold mb-1">{camDesc}</div>
            <div className="opacity-80 text-[10px] text-[#f59e0b]">
              ELEV: {camElev} | AZIM: {camAzim} | ZOOM: {camZoom}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
