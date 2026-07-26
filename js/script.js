// --- 1. CONFIGURAZIONE MAPPA ---
const map = L.map('map', {
    zoomControl: false,
    attributionControl: false,
    dragging: true,
    scrollWheelZoom: true,
    tap: false,       // Fix per touch/mobile
    inertia: true,
    worldCopyJump: true,
    Animations: true
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
    opacity: 1
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

let pendingAttachment = null;

// --- SESSIONE: id stabile per la memoria conversazionale dell'agente ---
function getSessionId() {
    let id = localStorage.getItem('aegis_session_id');
    if (!id) {
        id = (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : 'sess-' + Date.now() + '-' + Math.random().toString(16).slice(2);
        localStorage.setItem('aegis_session_id', id);
    }
    return id;
}

// --- CONVERSAZIONI ---
const API_BASE = 'http://localhost:8000';
let currentConversationId = null;

function getOperatorId() {
    return localStorage.getItem('aegis_operator_id') || 'ANONYMOUS';
}

async function createConversation() {
    const res = await fetch(`${API_BASE}/api/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator_id: getOperatorId() })
    });
    if (!res.ok) throw new Error('create failed');
    const conv = await res.json();
    currentConversationId = conv.id;
    clearChatHistory();
    await loadConversations();
    return conv;
}

function clearChatHistory() {
    const history = document.getElementById('chat-history');
    if (history) history.innerHTML = '';
    awaitingClarification = false;
}

// Icone SVG (Lucide) — mai emoji come icone strutturali
const ICON_RENAME = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg>`;
const ICON_DELETE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>`;

function updateArchiveCount(n) {
    const badge = document.getElementById('archive-count');
    if (badge) badge.innerText = String(n);
}

async function loadConversations() {
    const list = document.getElementById('conversation-list');
    if (!list) return;
    let items = [];
    try {
        const res = await fetch(`${API_BASE}/api/conversations?operator_id=${encodeURIComponent(getOperatorId())}`);
        if (!res.ok) throw new Error('list failed');
        items = await res.json();
    } catch (e) {
        list.innerHTML = '<div class="archive-empty">ARCHIVIO NON DISPONIBILE</div>';
        updateArchiveCount(0);
        return;
    }
    updateArchiveCount(items.length);
    list.innerHTML = '';
    if (items.length === 0) {
        list.innerHTML = '<div class="archive-empty">NESSUNA CONVERSAZIONE</div>';
        return;
    }
    items.forEach(conv => {
        const row = document.createElement('div');
        row.className = 'conversation-item' + (conv.id === currentConversationId ? ' active' : '');
        row.setAttribute('role', 'button');
        row.setAttribute('tabindex', '0');
        row.innerHTML = `<span class="title"></span>
            <span class="actions">
                <button type="button" class="btn-icon" data-act="rename" aria-label="Rinomina conversazione">${ICON_RENAME}</button>
                <button type="button" class="btn-icon is-danger" data-act="delete" aria-label="Elimina conversazione">${ICON_DELETE}</button>
            </span>`;
        row.querySelector('.title').innerText = conv.title;
        row.addEventListener('click', (ev) => {
            const actionBtn = ev.target.closest ? ev.target.closest('[data-act]') : null;
            const act = actionBtn ? actionBtn.dataset.act : null;
            if (act === 'rename') { ev.stopPropagation(); renameConversation(conv.id, conv.title); }
            else if (act === 'delete') { ev.stopPropagation(); deleteConversation(conv.id); }
            else { openConversation(conv.id); }
        });
        row.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openConversation(conv.id); }
        });
        list.appendChild(row);
    });
}

async function openConversation(id) {
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${id}/messages`);
        if (!res.ok) throw new Error('messages failed');
        const msgs = await res.json();
        currentConversationId = id;
        clearChatHistory();
        msgs.forEach(m => addMessage(m.content, m.role === 'user' ? 'user' : 'ai'));
        await loadConversations();
    } catch (e) {
        addMessage('ARCHIVIO NON DISPONIBILE: impossibile aprire la conversazione.', 'ai');
    }
}

async function renameConversation(id, currentTitle) {
    const title = prompt('Nuovo titolo:', currentTitle);
    if (title === null) return;
    if (!title.trim()) return;
    const res = await fetch(`${API_BASE}/api/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim() })
    });
    if (!res.ok) {
        addMessage('ARCHIVIO NON DISPONIBILE: impossibile rinominare la conversazione.', 'ai');
        return;
    }
    await loadConversations();
}

async function deleteConversation(id) {
    if (!confirm('Eliminare questa conversazione?')) return;
    const res = await fetch(`${API_BASE}/api/conversations/${id}`, { method: 'DELETE' });
    if (!res.ok) {
        addMessage('ARCHIVIO NON DISPONIBILE: impossibile eliminare la conversazione.', 'ai');
        return;
    }
    if (id === currentConversationId) {
        currentConversationId = null;
        clearChatHistory();
        try { await createConversation(); } catch (e) { /* DB offline: chat effimera */ }
        return;   // createConversation() already reloads the list
    }
    await loadConversations();
}

function setArchiveOpen(open) {
    const toggle = document.getElementById('archive-toggle');
    const panel = document.getElementById('archive-panel');
    if (!toggle || !panel) return;
    toggle.setAttribute('aria-expanded', String(open));
    panel.hidden = !open;
}

function isArchiveOpen() {
    const toggle = document.getElementById('archive-toggle');
    return toggle ? toggle.getAttribute('aria-expanded') === 'true' : false;
}

async function initConversations() {
    const btn = document.getElementById('new-chat-btn');
    if (btn) btn.addEventListener('click', () => createConversation().catch(() => {}));

    const toggle = document.getElementById('archive-toggle');
    if (toggle) toggle.addEventListener('click', () => setArchiveOpen(!isArchiveOpen()));

    await loadConversations();
    if (!currentConversationId) {
        try { await createConversation(); } catch (e) { /* DB offline: chat effimera */ }
    }
}

// --- Stato human-in-the-loop: true quando l'agente attende un chiarimento ---
let awaitingClarification = false;

initConversations();

function updateAttachmentBar() {
    const attachmentBar = document.getElementById('attachment-bar');
    const attachmentLabel = document.getElementById('attachment-label');

    if (!attachmentBar || !attachmentLabel) return;

    if (pendingAttachment) {
        attachmentLabel.innerText = pendingAttachment.name;
        attachmentBar.hidden = false;
    } else {
        attachmentLabel.innerText = 'ATTACHED IMAGE READY';
        attachmentBar.hidden = true;
    }
}

function clearAttachment() {
    pendingAttachment = null;
    const imageInput = document.getElementById('image-input');
    if (imageInput) imageInput.value = '';
    updateAttachmentBar();
}

function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Unable to read image file.'));
        reader.readAsDataURL(file);
    });
}

async function attachImageFile(file) {
    if (!file || !file.type.startsWith('image/')) return;

    const dataUrl = await fileToDataUrl(file);
    pendingAttachment = {
        name: file.name || 'screenshot.png',
        dataUrl: dataUrl,
        mimeType: file.type || 'image/png'
    };

    updateAttachmentBar();
}

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
function showChatLoader(type) {
    const history = document.getElementById('chat-history');
    if (!history) return;

    const loaderContainer = document.createElement('div');
    loaderContainer.id = 'active-chat-loader';
    loaderContainer.className = 'chat-loader-container';
    
    // Inseriamo lo spinner rosso definito nel CSS
    if (type === 'text')
        loaderContainer.innerHTML = '<div class="textLoader"></div>';
    else if (type === 'optic')
        loaderContainer.innerHTML = '<div class="opticLoader"></div>';
    else
        loaderContainer.innerHTML = '<div class="textLoader"></div>'; // Default
    
    
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
    if (!message && !pendingAttachment) return;

    const hasAttachment = Boolean(pendingAttachment);
    const displayMessage = message || (hasAttachment ? `ANALYZE ATTACHED IMAGE: ${pendingAttachment.name}` : '');

    // A. Mostra messaggio Utente
    addMessage(displayMessage, 'user');
    inputField.value = '';
    
    if (hasAttachment) {
        addMessage(`[IMAGE] ${pendingAttachment.name}`, 'user');
    }

    // B. Mostra Loader nella chat
    showChatLoader(hasAttachment ? 'optic' : 'text');

    try {
        // Vista corrente della mappa: per "qui/quest'area" e per il bias del geocoding
        const _center = map.getCenter();
        const _bounds = map.getBounds();
        const viewport = {
            lat: _center.lat, lon: _center.lng,
            north: _bounds.getNorth(), south: _bounds.getSouth(),
            east: _bounds.getEast(), west: _bounds.getWest()
        };

        const payload = {
            message: awaitingClarification ? '' : message,
            image_data: pendingAttachment ? pendingAttachment.dataUrl : null,
            image_name: pendingAttachment ? pendingAttachment.name : null,
            session_id: getSessionId(),
            resume: awaitingClarification ? message : null,
            viewport: viewport,
            conversation_id: currentConversationId,
        };

        // C. Chiamata API
        const response = await fetch('http://localhost:8000/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Uplink failed');
        const data = await response.json();

        // D. Rimuovi Loader
        removeChatLoader();
        clearAttachment();

        // E. Mostra Risposta AI
        addMessage(data.text, 'ai');

        // E-bis. Aggiorna lo stato di attesa chiarimento (human-in-the-loop)
        awaitingClarification = Boolean(data.awaiting_input);
        loadConversations();   // il titolo può essere appena stato generato

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
    showChatLoader('optic'); // Mostra loader

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
        // addMessage("SAT-LINK ERROR:", error.toString(), 'ai');
    }
}

// Funzione helper per aggiungere messaggi HTML alla chat
// --- Markdown rendering (markdown-it) + sanitizzazione (DOMPurify) ---
const md = window.markdownit({ breaks: true, linkify: true });
function renderMarkdown(text) {
    return DOMPurify.sanitize(md.render(text || ''));
}

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
        div.classList.add('msg-ai', 'mr-8', 'border-l-2', 'border-amber-400');
        div.innerHTML = `<strong class="text-amber-400 font-mono text-xs">[VISION_AI]</strong><br><div class="md">${renderMarkdown(text)}</div>`;
    } else {
        div.classList.add('msg-ai', 'mr-8');
        div.innerHTML = `<strong class="text-amber-500 font-mono text-xs">[OP_INTEL]</strong><br><div class="md">${renderMarkdown(text)}</div>`;
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

document.getElementById('attach-image-btn')?.addEventListener('click', () => {
    document.getElementById('image-input')?.click();
});

document.getElementById('image-input')?.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    try {
        await attachImageFile(file);
    } catch (error) {
        console.error('Attachment error:', error);
        addMessage('ATTACHMENT_ERROR: Impossibile leggere lo screenshot.', 'ai');
    }
});

document.getElementById('clear-attachment-btn')?.addEventListener('click', () => {
    clearAttachment();
});

document.getElementById('user-input')?.addEventListener('paste', async (event) => {
    const items = event.clipboardData?.items || [];
    const imageItem = Array.from(items).find((item) => item.type && item.type.startsWith('image/'));

    if (!imageItem) return;

    const file = imageItem.getAsFile();
    if (!file) return;

    event.preventDefault();

    try {
        await attachImageFile(file);
        addMessage(`SCREENSHOT PASTED: ${file.name || 'clipboard-image'}`, 'user');
    } catch (error) {
        console.error('Paste attachment error:', error);
        addMessage('ATTACHMENT_ERROR: Impossibile importare l\'immagine dagli appunti.', 'ai');
    }
});