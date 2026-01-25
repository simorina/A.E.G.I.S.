// --- INIZIALIZZAZIONE MAPPA ---
// Disabilita zoomControl default per pulizia (o spostalo se vuoi)
const map = L.map('map', {
    zoomControl: false,
    attributionControl: false
}).setView([45.4642, 9.1900], 13); // Zoom un po' più stretto per vedere dettagli satellite

// AGGIUNTA LAYER SATELLITARE (Esri World Imagery)
// Questo è il cambio fondamentale per il look "Operazione Militare"
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    maxZoom: 19
}).addTo(map);

// Aggiungiamo etichette stradali trasparenti sopra il satellite (Opzionale, ma utile)
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
    maxZoom: 19,
    opacity: 0.6 // Semitrasparente
}).addTo(map);

// Zoom Control posizionato in basso a destra
L.control.zoom({ position: 'bottomright' }).addTo(map);

let geoJsonLayer = null;

// --- HUD UPDATES ---
map.on('move', () => {
    const center = map.getCenter();
    document.getElementById('lat-disp').innerText = center.lat.toFixed(4);
    document.getElementById('lng-disp').innerText = center.lng.toFixed(4);
    document.getElementById('zoom-disp').innerText = map.getZoom();
});

// --- CHAT LOGIC ---
async function sendMessage() {
    const inputField = document.getElementById('user-input');
    const message = inputField.value;
    if (!message) return;

    // 1. UI Update
    addMessage(message, 'user');
    inputField.value = '';
    
    // Mostra Loader
    document.getElementById('loader').classList.remove('hidden');

    try {
        // Simulazione ritardo di rete (Rimuovere in prod)
        // await new Promise(r => setTimeout(r, 1200));

        // 2. API Call
        const response = await fetch('http://localhost:8000/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        // 3. Risposta
        addMessage(data.text, 'ai');

        if (data.geojson) {
            drawMapData(JSON.parse(data.geojson));
        }

    } catch (error) {
        console.error(error);
        addMessage("ERR_CONNECTION_TIMEOUT: Satellite uplink failed.", 'ai');
    } finally {
        // Nascondi Loader
        document.getElementById('loader').classList.add('hidden');
    }
}

function addMessage(text, sender) {
    const history = document.getElementById('chat-history');
    const div = document.createElement('div');
    
    if (sender === 'user') {
        div.className = "msg-user self-end";
        div.innerText = text;
    } else {
        div.className = "msg-ai";
        div.innerHTML = "<strong>OP_INTEL:</strong> " + text;
    }
    
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}

function drawMapData(geojsonData) {
    if (geoJsonLayer) map.removeLayer(geoJsonLayer);

    // Stile Tattico: Blu elettrico o Arancione per i dati sovrapposti al satellite
    geoJsonLayer = L.geoJSON(geojsonData, {
        style: function(feature) {
            return {
                color: "#3b82f6", // Blu tattico (Blue Team)
                weight: 3,
                opacity: 0.9,
                fillColor: "#3b82f6",
                fillOpacity: 0.2
            };
        },
        onEachFeature: function (feature, layer) {
            if (feature.properties) {
                let popupContent = "<div class='text-xs uppercase font-bold text-blue-400 mb-1'>Target Intel</div>";
                for (const [key, val] of Object.entries(feature.properties)) {
                    popupContent += `<div class='text-xs'>${key}: <span class='text-white'>${val}</span></div>`;
                }
                layer.bindPopup(popupContent);
            }
        },
        pointToLayer: function (feature, latlng) {
            return L.circleMarker(latlng, {
                radius: 8,
                fillColor: "#ef4444", // Punti rossi per target/interese
                color: "#fff",
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            });
        }
    }).addTo(map);

    if (geoJsonLayer.getBounds().isValid()) {
        map.fitBounds(geoJsonLayer.getBounds(), { padding: [100, 100] });
    }
}

function handleEnter(e) {
    if (e.key === 'Enter') sendMessage();
}

async function performScan() {
    // 1. Ottieni i confini attuali della mappa (BBox)
    const bounds = map.getBounds();
    const zoom = map.getZoom();

    const payload = {
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
        zoom: zoom
    };

    // UI Feedback
    addMessage("INIZIO SCANSIONE OTTICA SETTORE...", 'user');
    document.getElementById('loader').classList.remove('hidden');

    try {
        // 2. Chiamata API
        const response = await fetch('http://localhost:8000/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        // 3. Risposta
        if (data.text) {
             addMessage(data.text, 'ai-vision');
        } else {
             addMessage("SCAN FAILED: No visual intel retrieved.", 'ai');
        }

    } catch (error) {
        console.error(error);
        addMessage("ERR_UPLINK: Vision system offline.", 'ai');
    } finally {
        document.getElementById('loader').classList.add('hidden');
    }
}

// Modifica helper addMessage per gestire lo stile 'ai-vision'
function addMessage(text, sender) {
    const history = document.getElementById('chat-history');
    const div = document.createElement('div');
    
    if (sender === 'user') {
        div.className = "msg-user self-end";
        div.innerText = text;
    } else if (sender === 'ai-vision') {
        div.className = "msg-ai border-l-2 border-blue-500 bg-blue-900/10";
        div.innerHTML = "<strong class='text-blue-400'>VISION_AI:</strong> " + text;
    } else {
        div.className = "msg-ai";
        div.innerHTML = "<strong>OP_INTEL:</strong> " + text;
    }
    
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}