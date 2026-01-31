// --- 1. CONFIGURAZIONE MAPPA ---
const map = L.map('map', {
    zoomControl: false,
    attributionControl: false,
    dragging: true,
    scrollWheelZoom: true,
    tap: false,       // Fix per touch/mobile
    inertia: true,
    worldCopyJump: true
}).setView([45.4642, 9.1900], 13);

// --- 2. FIX INTERAZIONE E RESIZE ---
const mapContainer = document.getElementById('map');

// Forza il focus sulla mappa al click per evitare blocchi
mapContainer.addEventListener('mousedown', () => {
    map.getContainer().focus();
});

// Aggiungi classi CSS per cambiare cursore durante il drag
map.on('dragstart', () => { mapContainer.style.cursor = 'grabbing'; });
map.on('dragend', () => { mapContainer.style.cursor = 'grab'; });

// Aggiorna dimensioni mappa periodicamente (previeni glitch di rendering)
setInterval(() => {
    map.invalidateSize();
}, 2000);

// --- 3. LAYERS TILE ---
// Satellite Layer
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19
}).addTo(map);

// Etichette (Strade/Città)
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
    maxZoom: 19,
    opacity: 0.6
}).addTo(map);

// Controllo Zoom in basso a destra
L.control.zoom({ position: 'bottomright' }).addTo(map);

// Layer GeoJSON per i dati tattici
let geoJsonLayer = null;

// --- 4. HUD E UTILITIES ---
// Aggiorna coordinate lat/lng a schermo
map.on('move', () => {
    const center = map.getCenter();
    const latDisp = document.getElementById('lat-disp');
    const lngDisp = document.getElementById('lng-disp');
    
    if(latDisp) latDisp.innerText = center.lat.toFixed(4);
    if(lngDisp) lngDisp.innerText = center.lng.toFixed(4);
});

// Gestione Preloader Globale (Pagina Intera)
window.addEventListener('load', () => {
    const globalLoader = document.getElementById('global-loader');
    // Aspetta 1.5 secondi per effetto scenico poi sfuma
    setTimeout(() => {
        globalLoader.classList.add('fade-out');
        // Rimuovi dal DOM dopo l'animazione
        setTimeout(() => { globalLoader.remove(); }, 600); 
    }, 1500);
});

// --- 5. LOGICA LOADER CHAT ---
// Funzione per creare e appendere lo spinner dentro la chat history
function showChatLoader() {
    const history = document.getElementById('chat-history');
    if (!history) return;

    const loaderContainer = document.createElement('div');
    loaderContainer.id = 'active-chat-loader';
    loaderContainer.className = 'chat-loader-container';
    
    // Inseriamo lo spinner rosso definito nel CSS
    loaderContainer.innerHTML = '<div class="loader"></div>';
    
    history.appendChild(loaderContainer);
    history.scrollTop = history.scrollHeight; // Scroll automatico in basso
}

// Funzione per rimuovere lo spinner
function removeChatLoader() {
    const loader = document.getElementById('active-chat-loader');
    if (loader) loader.remove();
}

// --- 6. FUNZIONI CHAT & AGENT ---

async function sendMessage() {
    const inputField = document.getElementById('user-input');
    if (!inputField) return;
    
    const message = inputField.value.trim();
    if (!message) return;

    // A. Mostra messaggio Utente
    addMessage(message, 'user');
    inputField.value = '';
    
    // B. Mostra Loader nella chat
    showChatLoader();

    try {
        // C. Chiamata API
        const response = await fetch('http://localhost:8000/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) throw new Error('Uplink failed');
        const data = await response.json();

        // D. Rimuovi Loader
        removeChatLoader();

        // E. Mostra Risposta AI
        addMessage(data.text, 'ai');

        // F. Disegna Dati su Mappa se presenti
        if (data.geojson) {
            drawMapData(JSON.parse(data.geojson));
        }

    } catch (error) {
        removeChatLoader(); // Rimuovi loader anche in caso di errore
        console.error("SAT-LINK ERROR:", error);
        addMessage("ERR_SIGNAL_LOST: Impossibile contattare il comando centrale.", 'ai');
    }
}

async function performScan() {
    const bounds = map.getBounds();
    const payload = {
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
        zoom: map.getZoom()
    };

    addMessage("STARTING OPTIC SCANNING...", 'user');
    showChatLoader(); // Mostra loader

    try {
        const response = await fetch('http://localhost:8000/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        removeChatLoader(); // Nascondi loader
        addMessage(data.text || "Scansione completata. Nessuna minaccia rilevata.", 'ai-vision');

    } catch (error) {
        removeChatLoader();
        addMessage("SCAN_ERROR: Sensori offline.", 'ai');
    }
}

// Funzione helper per aggiungere messaggi HTML alla chat
function addMessage(text, sender) {
    const history = document.getElementById('chat-history');
    if (!history) return;
    // Crea il div del messaggio
    const div = document.createElement('div');
    div.className = "mb-4 p-3 text-sm font-['Chakra_Petch']";
    // Stile differenziato per Utente e AI
    if (sender === 'user') {
        div.classList.add('msg-user', 'self-end', 'ml-8');
        div.innerText = `> ${text}`;
    } else if (sender === 'ai-vision') {
        div.classList.add('msg-ai', 'mr-8', 'border-l-2', 'border-blue-500');
        div.innerHTML = `<strong class="text-blue-400 font-mono text-xs">[VISION_AI]</strong><br>${text}`;
    } else {
        div.classList.add('msg-ai', 'mr-8');
        div.innerHTML = `<strong class="text-amber-500 font-mono text-xs">[OP_INTEL]</strong><br>${text}`;
    }
    
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}

// --- 7. RENDERING DATI SU MAPPA ---
function drawMapData(geojsonData) {
    if (geoJsonLayer) map.removeLayer(geoJsonLayer);

    console.log("SAT-LINK: Rendering dati tattici...", geojsonData);

    // Configurazione Layer GeoJSON
    geoJsonLayer = L.geoJSON(geojsonData, {
        style: {
            color: "#f59e0b", // Ambra
            weight: 2,
            opacity: 0.8,
            fillColor: "#f59e0b",
            fillOpacity: 0.1
        },
        // Personalizza i marker per i punti
        pointToLayer: function (feature, latlng) {
            return L.circleMarker(latlng, {
                radius: 8,
                fillColor: "#000",
                color: "#f59e0b",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9,
                interactive: true // Fondamentale per il click
            });
        },
        // Popup con dati tattici
        onEachFeature: function (feature, layer) {
            if (feature.properties) {
                // Generazione HTML Popup Tattico
                let html = `<div class="popup-header"><span>TARGET DATA</span></div>`;
                html += `<div class="popup-body">`;
                
                for (const [key, val] of Object.entries(feature.properties)) {
                    // Filtra campi nulli o ID interni per pulizia
                    if (val !== null && val !== "" && key !== 'id' && key !== 'geom') { 
                        html += `
                        <div class="data-row">
                            <span class="data-label">${key}</span>
                            <span class="data-value">${val}</span>
                        </div>`;
                    }
                }
                html += `</div>`;

                layer.bindPopup(html, {
                    maxWidth: 320,
                    minWidth: 220,
                    className: 'military-popup-container'
                });
            }
        }
    }).addTo(map);

    // Zoom automatico sui risultati
    if (geoJsonLayer.getBounds().isValid()) {
        map.fitBounds(geoJsonLayer.getBounds(), { padding: [100, 100] });
    }
}

// Gestione Invio con tasto Enter
document.getElementById('user-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});