
import * as THREE from 'three';
        import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
        import { MeshSurfaceSampler } from 'three/addons/math/MeshSurfaceSampler.js';
        import { OrbitControls } from 'three/addons/controls/OrbitControls.js'; 

        // --- Configuration ---
        const PARTICLE_COUNT = 150000; 
        const MODEL_NAMES = ['b2/scene.gltf', 'jet/scene.gltf', 'sat/scene.gltf','uav/scene.gltf','helic/scene.gltf']; 
        const FOLDER_PATH = 'models/'; 
        
        // --- Globals ---
        let scene, camera, renderer, points, controls;
        let modelPositions = []; 
        let currentIdx = 0;
        const container = document.getElementById('canvas-container');

        // --- Glitch Effect Class ---
        class TextScramble {
            constructor(el) {
                this.el = el;
                this.chars = '!<>-_\\/[]{}—=+*^?#________';
                this.update = this.update.bind(this);
            }
            setText(newText) {
                const oldText = this.el.innerText;
                const length = Math.max(oldText.length, newText.length);
                const promise = new Promise((resolve) => this.resolve = resolve);
                this.queue = [];
                for (let i = 0; i < length; i++) {
                    const from = oldText[i] || '';
                    const to = newText[i] || '';
                    const start = Math.floor(Math.random() * 40);
                    const end = start + Math.floor(Math.random() * 40);
                    this.queue.push({ from, to, start, end });
                }
                cancelAnimationFrame(this.frameRequest);
                this.frame = 0;
                this.update();
                return promise;
            }
            update() {
                let output = '';
                let complete = 0;
                for (let i = 0, n = this.queue.length; i < n; i++) {
                    let { from, to, start, end, char } = this.queue[i];
                    if (this.frame >= end) {
                        complete++;
                        output += to;
                    } else if (this.frame >= start) {
                        if (!char || Math.random() < 0.28) {
                            char = this.randomChar();
                            this.queue[i].char = char;
                        }
                        output += `<span style="opacity: 0.5">${char}</span>`;
                    } else {
                        output += from;
                    }
                }
                this.el.innerHTML = output;
                if (complete === this.queue.length) {
                    this.resolve();
                } else {
                    this.frameRequest = requestAnimationFrame(this.update);
                    this.frame++;
                }
            }
            randomChar() {
                return this.chars[Math.floor(Math.random() * this.chars.length)];
            }
        }

        // --- Init Function ---
        async function init() {
            scene = new THREE.Scene();
            scene.fog = new THREE.FogExp2(0x050505, 0.05);

            camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.position.set(3,3,3); // Offset slightly to look "tactical"

            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            container.appendChild(renderer.domElement);

            // --- CONTROLS SETUP ---
            controls = new OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true; // Smooths the rotation
            controls.dampingFactor = 0.05;
            controls.enableZoom = true;   // Disable zoom to keep UI consistent
            controls.enablePan = false;    // Disable panning to keep model centered
            controls.autoRotate = true;    // Keep it alive
            controls.autoRotateSpeed = 0.5; // Very slow rotation
            
            // Allow user to interact
            controls.update();

            const loader = new GLTFLoader();

            try {
                // Carica tutti i modelli e campiona le posizioni
                for (const name of MODEL_NAMES) {
                    const gltf = await loader.loadAsync(FOLDER_PATH + name);
                    const posArray = new Float32Array(PARTICLE_COUNT * 3);
                    sampleAndNormalize(gltf.scene, posArray);
                    modelPositions.push(posArray);
                }

                // Dopo aver caricato tutti i modelli, crea i punti e avvia l'animazione
                if(modelPositions.length > 0) {
                    createPoints();
                    setInterval(() => {
                        currentIdx = (currentIdx + 1) % modelPositions.length;
                    }, 6000);
                }
                
                animate();

            } catch (err) {
                console.warn("Model load failed or waiting for models. Using fallback sphere.");
                const sphereGeo = new THREE.SphereGeometry(1, 128, 128);
                const posArray = new Float32Array(PARTICLE_COUNT * 3);
                const tempPos = sphereGeo.attributes.position.array;
                const sampler = new MeshSurfaceSampler(new THREE.Mesh(sphereGeo)).build();
                const _v = new THREE.Vector3();
                for (let i = 0; i < PARTICLE_COUNT; i++) {
                    sampler.sample(_v);
                    posArray[i*3] = _v.x * 2.5;
                    posArray[i*3+1] = _v.y * 2.5;
                    posArray[i*3+2] = _v.z * 2.5;
                }
                modelPositions.push(posArray);
                createPoints();
                animate();
            }
        }

        function calculateSurfaceArea(mesh) {
            // Calcola l'area superficiale di una mesh per il campionamento proporzionale
            const geometry = mesh.geometry;
            // Assumiamo che la geometria sia composta da triangoli (standard per GLTF)
            const position = geometry.attributes.position;
            // Se la geometria è indicizzata, usiamo l'index per accedere ai vertici
            const index = geometry.index;
            // Variabili temporanee per i calcoli
            let area = 0;
            // Vettori per i vertici del triangolo e per i calcoli intermedi
            const pA = new THREE.Vector3(), pB = new THREE.Vector3(), pC = new THREE.Vector3();
            // Vettori per il calcolo dell'area del triangolo
            const ab = new THREE.Vector3(), ac = new THREE.Vector3(), cross = new THREE.Vector3();

            // Se la geometria è indicizzata (ottimizzata)
            if (index) {
                // Itera sui triangoli usando l'index
                for (let i = 0; i < index.count; i += 3) {
                    pA.fromBufferAttribute(position, index.getX(i));
                    pB.fromBufferAttribute(position, index.getX(i + 1));
                    pC.fromBufferAttribute(position, index.getX(i + 2));
                    
                    // Area triangolo = 0.5 * |AB x AC|
                    ab.subVectors(pB, pA);
                    ac.subVectors(pC, pA);
                    cross.crossVectors(ab, ac);
                    area += cross.length() * 0.5;
                }
            } else {
                // Se non è indicizzata
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
            
            // Applica la scala dell'oggetto all'area (approssimazione uniforme)
            // Questo serve se l'artista ha scalato la mesh nell'editor 3D
            const scale = mesh.getWorldScale(new THREE.Vector3());
            area *= scale.x * scale.y; // Approssimazione rapida per la scala
            return area;
        }

    function sampleAndNormalize(model, targetArray) {
        // 1. Trova tutte le mesh e calcola l'area totale
        let meshes = [];
        let totalArea = 0;
        
        // Importante: aggiorniamo le matrici globali per leggere la posizione corretta delle parti
        model.updateMatrixWorld(true);

        // Attraversiamo tutte le parti del modello per trovare le mesh e calcolare l'area totale
        model.traverse(n => { 
            if(n.isMesh) {
                // Clona la mesh per non alterare l'originale durante i calcoli
                // ma mantieni il riferimento alla matrixWorld
                meshes.push(n);
                totalArea += calculateSurfaceArea(n);
            }
        });

        // 2. Calcola il bounding box globale per centrare tutto alla fine
        const box = new THREE.Box3().setFromObject(model);
        const size = new THREE.Vector3();
        box.getSize(size);
        const center = new THREE.Vector3();
        box.getCenter(center);
        
        const maxDim = Math.max(size.x, size.y, size.z);
        const scaleFactor = 4.5 / maxDim; // Scala target per la visualizzazione
        
        // Offset per centrare il modello
        const offX = center.x;
        const offY = center.y;
        const offZ = center.z;

        let arrayIndex = 0;
        const _v = new THREE.Vector3();
        
        // 3. Itera su ogni mesh e campiona proporzionalmente
        meshes.forEach(mesh => {
            // Quanti punti assegnare a questa parte? (Area Parte / Area Totale) * Totale Punti
            const meshArea = calculateSurfaceArea(mesh);
            let numParticles = Math.floor((meshArea / totalArea) * PARTICLE_COUNT);
            
            // Evitiamo parti con 0 punti se sono troppo piccole ma visibili
            if (numParticles === 0 && meshArea > 0) numParticles = 1;
            
            // Se la mesh è troppo piccola o ha problemi, salta il campionamento
            if (numParticles > 0) {
                const sampler = new MeshSurfaceSampler(mesh).build();
                
                for (let i = 0; i < numParticles; i++) {
                    // Sicurezza per non sforare l'array
                    if (arrayIndex >= PARTICLE_COUNT * 3) break;

                    sampler.sample(_v);
                    
                    // IMPORTANTE: Convertiamo il punto dallo spazio locale della mesh allo spazio globale
                    // Altrimenti le parti dell'elicottero collassano tutte al centro (0,0,0)
                    _v.applyMatrix4(mesh.matrixWorld);

                    // Ora applichiamo la normalizzazione (centramento e scala globale)
                    targetArray[arrayIndex]     = (_v.x - offX) * scaleFactor;
                    targetArray[arrayIndex + 1] = (_v.y - offY) * scaleFactor;
                    targetArray[arrayIndex + 2] = (_v.z - offZ) * scaleFactor;
                    
                    arrayIndex += 3;
                }
            }
        });

        // Riempie eventuali buchi finali (se l'arrotondamento ha lasciato spazi vuoti) riciclando l'ultimo punto
        // Questo evita glitch grafici se arrayIndex < PARTICLE_COUNT * 3
        while(arrayIndex < PARTICLE_COUNT * 3) {
            targetArray[arrayIndex] = targetArray[arrayIndex-3] || 0;
            targetArray[arrayIndex+1] = targetArray[arrayIndex-2] || 0;
            targetArray[arrayIndex+2] = targetArray[arrayIndex-1] || 0;
            arrayIndex += 3;
        }
    }

        function createPoints() {
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(modelPositions[0]), 3));
            
            const mat = new THREE.PointsMaterial({
                color: new THREE.Color("rgb(245, 158, 11)"),
                size: 0.008,
                transparent: true,
                opacity: 0.8,
                blending: THREE.AdditiveBlending,
                sizeAttenuation: true
            });

            points = new THREE.Points(geo, mat);
            scene.add(points);
        }

        function animate() {
            requestAnimationFrame(animate);

            // Update Controls (Required for damping and auto-rotate)
            if (controls) controls.update();

            if (points) {
                const positions = points.geometry.attributes.position.array;
                const targetSet = modelPositions[currentIdx];

                // Morphing Logic
                for (let i = 0; i < PARTICLE_COUNT * 3; i++) {
                    positions[i] += (targetSet[i] - positions[i]) * 0.03;
                }
                points.geometry.attributes.position.needsUpdate = true;
                
                // Note: We removed the manual points.rotation lines here.
                // Rotation is now handled entirely by the Camera via OrbitControls.
            }

            renderer.render(scene, camera);
        }

        // --- Event Listeners ---

        window.addEventListener('resize', () => {
            const w = container.clientWidth;
            const h = container.clientHeight;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        });

        // Text Scramble on Load
        window.addEventListener('load', () => {
            const el = document.querySelector('#title-glitch');
            const fx = new TextScramble(el);
            fx.setText('INTEL_CORE_v8.4');
        });

        // Random Hex Updater
        setInterval(() => {
            const addr = document.getElementById('mem-addr');
            addr.innerText = '0x' + Math.floor(Math.random()*16777215).toString(16).toUpperCase().substring(0, 4);
        }, 150);

        init();
        
        
