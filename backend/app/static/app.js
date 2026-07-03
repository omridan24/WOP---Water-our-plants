/*
 * WOP - Water Our Plants | Dashboard Logic
 */

// ─── State ────────────────────────────────────────────────────────
let plants = [];
let currentPlant = null;
let currentChart = null;
let ws = null;

// ─── DOM Elements ──────────────────────────────────────────────────
const els = {
    // Views
    plantGrid: document.getElementById('plant-grid'),
    deviceGrid: document.getElementById('device-grid'),
    emptyState: document.getElementById('empty-state'),
    detailView: document.getElementById('plant-detail'),
    
    // Tabs
    tabPlants: document.getElementById('tab-plants'),
    tabDevices: document.getElementById('tab-devices'),
    
    // Add Plant Modal
    addModal: document.getElementById('add-plant-modal'),
    addForm: document.getElementById('add-plant-form'),
    imageInput: document.getElementById('plant-image'),
    imagePreview: document.getElementById('image-preview'),
    uploadPlaceholder: document.getElementById('upload-placeholder'),
    uploadZone: document.getElementById('image-upload-zone'),
    btnScanBle: document.getElementById('btn-scan-ble'),
    bleScanResults: document.getElementById('ble-scan-results'),
    
    // Detail View Elements
    detailImage: document.getElementById('detail-image'),
    detailName: document.getElementById('detail-name'),
    detailSpecies: document.getElementById('detail-species'),
    detailLight: document.getElementById('detail-light'),
    detailWatering: document.getElementById('detail-watering'),
    detailNotes: document.getElementById('detail-notes'),
    detailBleBadge: document.getElementById('detail-ble-badge'),
    
    // Gauges
    moistureValue: document.getElementById('gauge-moisture-value'),
    moistureFill: document.getElementById('gauge-moisture-fill'),
    moistureRange: document.getElementById('gauge-moisture-range'),
    waterValue: document.getElementById('gauge-water-value'),
    waterFill: document.getElementById('gauge-water-fill'),
    
    // Pump
    pumpStateText: document.getElementById('pump-state-text'),
    pumpIcon: document.getElementById('pump-icon'),
    btnPumpOn: document.getElementById('btn-pump-on'),
    btnPumpOff: document.getElementById('btn-pump-off'),
    
    // Chart
    chartCanvas: document.getElementById('history-chart'),
    chartTabs: document.querySelectorAll('.chart-period-tabs .tab'),
    
    // Info
    infoBle: document.getElementById('detail-ble-address'),
    infoUptime: document.getElementById('detail-uptime'),
    infoConnection: document.getElementById('detail-connection-status'),
    
    // Header
    bleIndicator: document.getElementById('ble-indicator'),
    bleStatusText: document.getElementById('ble-status-text')
};

const GAUGE_CIRCUMFERENCE = 326.73;

// ─── Initialization ────────────────────────────────────────────────
async function init() {
    setupEventListeners();
    await fetchPlants();
    setInterval(updateOverallBleStatus, 10000);
    updateOverallBleStatus();
}

function setupEventListeners() {
    // Navigation Tabs
    els.tabPlants.addEventListener('click', () => switchView('plants'));
    els.tabDevices.addEventListener('click', () => switchView('devices'));
    
    document.getElementById('btn-back').addEventListener('click', () => switchView('plants'));
    document.getElementById('btn-add-plant').addEventListener('click', () => showAddModal());
    document.getElementById('btn-add-first').addEventListener('click', () => showAddModal());
    
    // Add Modal
    document.getElementById('modal-close').addEventListener('click', hideAddModal);
    document.getElementById('btn-cancel-add').addEventListener('click', hideAddModal);
    els.addForm.addEventListener('submit', handleAddPlantSubmit);
    
    // Image Upload UX
    els.uploadZone.addEventListener('click', () => els.imageInput.click());
    els.imageInput.addEventListener('change', handleImageSelect);
    els.uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        els.uploadZone.classList.add('dragging');
    });
    els.uploadZone.addEventListener('dragleave', () => els.uploadZone.classList.remove('dragging'));
    els.uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        els.uploadZone.classList.remove('dragging');
        if (e.dataTransfer.files.length) {
            els.imageInput.files = e.dataTransfer.files;
            handleImageSelect();
        }
    });
    
    // BLE Scan
    els.btnScanBle.addEventListener('click', () => handleBleScan('plant-ble-address', 'ble-scan-results', els.btnScanBle));
    document.getElementById('btn-scan-ble-edit').addEventListener('click', () => handleBleScan('edit-ble', 'ble-scan-results-edit', document.getElementById('btn-scan-ble-edit')));
    
    // Pump Controls
    els.btnPumpOn.addEventListener('click', () => sendPumpCommand('on'));
    els.btnPumpOff.addEventListener('click', () => sendPumpCommand('off'));
    
    // Chart Tabs
    els.chartTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            els.chartTabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            if (currentPlant) {
                loadChartData(currentPlant.id, parseInt(e.target.dataset.hours));
            }
        });
    });

    // Delete Plant
    document.getElementById('btn-delete-plant').addEventListener('click', async () => {
        if (!currentPlant) return;
        if (confirm(`Are you sure you want to delete ${currentPlant.name}?`)) {
            try {
                await fetch(`/api/plants/${currentPlant.id}`, { method: 'DELETE' });
                switchView('plants');
            } catch (err) {
                console.error("Failed to delete plant:", err);
                alert("Failed to delete plant");
            }
        }
    });

    // Edit Modal (Simplified logic here - basic close/cancel)
    document.getElementById('btn-edit-plant').addEventListener('click', showEditModal);
    document.getElementById('edit-modal-close').addEventListener('click', hideEditModal);
    document.getElementById('btn-cancel-edit').addEventListener('click', hideEditModal);
    document.getElementById('edit-plant-form').addEventListener('submit', handleEditPlantSubmit);
}

// ─── API Calls ─────────────────────────────────────────────────────
async function fetchPlants() {
    try {
        const res = await fetch('/api/plants');
        plants = await res.json();
        
        // If we are on the plants view, render it
        if (els.tabPlants.classList.contains('active') && els.detailView.style.display === 'none') {
            renderPlantGrid();
        }
    } catch (err) {
        console.error("Failed to fetch plants:", err);
    }
}

async function fetchPlantDetails(id) {
    try {
        const res = await fetch(`/api/plants/${id}`);
        return await res.json();
    } catch (err) {
        console.error("Failed to fetch plant details:", err);
        return null;
    }
}

async function updateOverallBleStatus() {
    try {
        const res = await fetch('/api/ble/status');
        const data = await res.json();
        const devices = data.devices;
        
        let connectedCount = devices.filter(d => d.connected).length;
        
        els.bleIndicator.className = 'ble-indicator';
        if (devices.length === 0) {
            els.bleStatusText.textContent = "No devices";
            els.bleIndicator.classList.add('disconnected');
        } else if (connectedCount === devices.length) {
            els.bleStatusText.textContent = `BLE: All Good (${connectedCount}/${devices.length})`;
            els.bleIndicator.classList.add('connected');
        } else if (connectedCount > 0) {
            els.bleStatusText.textContent = `BLE: Partial (${connectedCount}/${devices.length})`;
            els.bleIndicator.classList.add('partial');
        } else {
            els.bleStatusText.textContent = `BLE: Offline (0/${devices.length})`;
            els.bleIndicator.classList.add('disconnected');
        }
        
        // If we are on the devices view, refresh it
        if (els.tabDevices.classList.contains('active')) {
            renderDeviceGrid(devices);
        }
    } catch (e) {
        console.error("Failed to get BLE status", e);
    }
}

// ─── UI Rendering ──────────────────────────────────────────────────
function switchView(view) {
    if (ws) {
        ws.close();
        ws = null;
    }
    currentPlant = null;
    els.detailView.style.display = 'none';
    
    if (view === 'plants') {
        els.tabPlants.classList.add('active');
        els.tabDevices.classList.remove('active');
        els.deviceGrid.style.display = 'none';
        fetchPlants().then(() => renderPlantGrid());
    } else if (view === 'devices') {
        els.tabDevices.classList.add('active');
        els.tabPlants.classList.remove('active');
        els.plantGrid.style.display = 'none';
        els.emptyState.style.display = 'none';
        els.deviceGrid.style.display = 'grid';
        fetch('/api/ble/status')
            .then(res => res.json())
            .then(data => renderDeviceGrid(data.devices));
    }
}

function renderPlantGrid() {
    if (plants.length === 0) {
        els.plantGrid.style.display = 'none';
        els.emptyState.style.display = 'block';
        return;
    }
    
    els.emptyState.style.display = 'none';
    els.plantGrid.style.display = 'grid';
    els.plantGrid.innerHTML = '';
    
    plants.forEach(plant => {
        const card = document.createElement('div');
        card.className = 'plant-card';
        card.onclick = () => openPlantDetail(plant.id);
        
        const imgHtml = plant.image_url 
            ? `<img src="${plant.image_url}" alt="${plant.name}" class="plant-card-image">`
            : `<div class="plant-card-image-placeholder">🌿</div>`;
            
        const isConnected = plant.ble_connected;
        const connClass = isConnected ? 'online' : 'offline';
        const connText = isConnected ? 'Online' : 'Offline';
        
        let moistureText = '--%';
        let waterText = '--%';
        let moistureClass = 'muted';
        let waterClass = 'muted';
        
        if (plant.latest_reading) {
            moistureText = `${plant.latest_reading.soil_moisture_pct}%`;
            waterText = `${plant.latest_reading.water_depth_pct}%`;
            moistureClass = '';
            waterClass = 'blue';
        }
        
        card.innerHTML = `
            ${imgHtml}
            <div class="plant-card-connection ${connClass}">
                <div class="connection-dot ${connClass}"></div>
                ${connText}
            </div>
            <div class="plant-card-body">
                <div class="plant-card-name">${plant.name}</div>
                <div class="plant-card-species">${plant.species || 'Unknown species'}</div>
                <div class="plant-card-stats">
                    <div class="stat">
                        <span class="stat-icon">💧</span>
                        <span class="stat-value ${moistureClass}">${moistureText}</span>
                    </div>
                    <div class="stat">
                        <span class="stat-icon">🌊</span>
                        <span class="stat-value ${waterClass}">${waterText}</span>
                    </div>
                </div>
            </div>
        `;
        els.plantGrid.appendChild(card);
    });
}

function renderDeviceGrid(devices) {
    els.deviceGrid.innerHTML = '';
    
    if (devices.length === 0) {
        els.deviceGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-icon">📡</div>
                <h2>No Arduino Devices Found</h2>
                <p>Assign a BLE address to a plant to register a device.</p>
            </div>
        `;
        return;
    }
    
    devices.forEach(d => {
        const card = document.createElement('div');
        card.className = 'device-card';
        
        const connClass = d.connected ? 'online' : 'offline';
        const connText = d.connected ? 'Connected' : 'Disconnected';
        
        let plantsHtml = '';
        if (d.plant_ids && d.plant_ids.length > 0) {
            d.plant_ids.forEach(pid => {
                const p = plants.find(plant => plant.id === pid);
                if (p) {
                    plantsHtml += `
                        <div class="device-plant-item">
                            🌿 ${p.name}
                        </div>
                    `;
                }
            });
        } else {
            plantsHtml = '<div class="device-plant-item" style="color:var(--text-muted)">No plants assigned</div>';
        }
        
        card.innerHTML = `
            <div class="device-card-header">
                <div class="device-name">📡 ${d.device_name}</div>
                <div class="plant-card-connection ${connClass}" style="position:static; margin:0;">
                    <div class="connection-dot ${connClass}"></div>
                    ${connText}
                </div>
            </div>
            <div class="device-address">${d.address}</div>
            
            <div class="device-plants-list">
                <h4>Assigned Plants</h4>
                ${plantsHtml}
            </div>
        `;
        els.deviceGrid.appendChild(card);
    });
}

// ─── Detail View ───────────────────────────────────────────────────
async function openPlantDetail(id) {
    const plant = await fetchPlantDetails(id);
    if (!plant) return;
    
    currentPlant = plant;
    
    // Hide grid, show detail
    els.plantGrid.style.display = 'none';
    els.deviceGrid.style.display = 'none';
    els.emptyState.style.display = 'none';
    els.detailView.style.display = 'block';
    
    // Populate header info
    if (plant.image_url) {
        els.detailImage.src = plant.image_url;
        els.detailImage.style.display = 'block';
    } else {
        els.detailImage.style.display = 'none';
    }
    
    els.detailName.textContent = plant.name;
    els.detailSpecies.textContent = plant.species || 'Unknown species';
    els.detailLight.innerHTML = `☀️ ${plant.light_preference || '--'}`;
    els.detailWatering.innerHTML = `💧 ${plant.watering_frequency || '--'}`;
    els.detailNotes.textContent = plant.notes || 'No care notes available.';
    
    els.detailBleBadge.innerHTML = plant.ble_connected ? '📡 Online' : '📡 Offline';
    els.detailBleBadge.style.color = plant.ble_connected ? 'var(--green-primary)' : 'var(--text-muted)';
    
    els.infoBle.textContent = plant.ble_address || 'Not configured';
    
    els.moistureRange.textContent = `Ideal: ${plant.ideal_moisture_min}% - ${plant.ideal_moisture_max}%`;
    
    // Set initial gauges
    if (plant.latest_reading) {
        updateGauges(plant.latest_reading, plant.ble_connected);
    } else {
        updateGauges(null, plant.ble_connected);
    }
    
    // Setup Chart
    const activeTab = document.querySelector('.chart-period-tabs .tab.active');
    const hours = activeTab ? parseInt(activeTab.dataset.hours) : 24;
    renderChart(plant.recent_readings || []);
    
    // Start WebSocket
    connectWebSocket(plant.id);
}

// ─── Real-time Updates ─────────────────────────────────────────────
function updateGauges(data, isConnected) {
    els.infoConnection.textContent = isConnected ? 'Connected' : 'Disconnected';
    els.infoConnection.style.color = isConnected ? 'var(--green-primary)' : 'var(--red)';
    
    if (!data) {
        setGauge(els.moistureFill, els.moistureValue, 0, '--%');
        setGauge(els.waterFill, els.waterValue, 0, '--%');
        els.infoUptime.textContent = '--';
        setPumpState(false);
        return;
    }
    
    setGauge(els.moistureFill, els.moistureValue, data.soil_moisture_pct, `${data.soil_moisture_pct}%`);
    setGauge(els.waterFill, els.waterValue, data.water_depth_pct, `${data.water_depth_pct}%`);
    
    // Uptime formatting
    const mins = Math.floor(data.uptime_seconds / 60);
    const hrs = Math.floor(mins / 60);
    els.infoUptime.textContent = `${hrs}h ${mins % 60}m`;
    
    setPumpState(data.pump_active);
}

function setGauge(fillEl, textEl, pct, text) {
    const constrainedPct = Math.max(0, Math.min(100, pct));
    const offset = GAUGE_CIRCUMFERENCE - (constrainedPct / 100) * GAUGE_CIRCUMFERENCE;
    fillEl.style.strokeDashoffset = offset;
    textEl.textContent = text;
}

function setPumpState(isActive) {
    if (isActive) {
        els.pumpStateText.textContent = "ON";
        els.pumpStateText.classList.add('active');
        els.pumpIcon.classList.add('spinning');
        els.btnPumpOn.disabled = true;
        els.btnPumpOff.disabled = false;
    } else {
        els.pumpStateText.textContent = "OFF";
        els.pumpStateText.classList.remove('active');
        els.pumpIcon.classList.remove('spinning');
        els.btnPumpOn.disabled = false;
        els.btnPumpOff.disabled = true;
    }
}

async function sendPumpCommand(action) {
    if (!currentPlant) return;
    try {
        const res = await fetch(`/api/plants/${currentPlant.id}/pump`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        if (!res.ok) {
            const data = await res.json();
            alert(`Pump error: ${data.detail || 'Unknown error'}`);
        }
    } catch (err) {
        console.error("Pump command failed", err);
    }
}

// ─── WebSocket ─────────────────────────────────────────────────────
function connectWebSocket(plantId) {
    if (ws) ws.close();
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/plants/${plantId}/live`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'sensor_data') {
            updateGauges(msg.data, msg.ble_connected);
            // Optionally, append to chart in real-time
            if (currentChart && msg.data) {
                appendDataToChart(msg.data);
            }
        } else if (msg.type === 'status') {
            updateGauges(null, msg.ble_connected);
        } else if (msg.type === 'ping') {
            ws.send("pong");
        }
    };
    
    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
    
    ws.onclose = () => {
        console.log("WebSocket closed");
        // Could implement reconnection logic here if detail view is still open
    };
}

// ─── Chart.js ──────────────────────────────────────────────────────
async function loadChartData(plantId, hours) {
    try {
        const res = await fetch(`/api/plants/${plantId}/readings?hours=${hours}`);
        const data = await res.json();
        renderChart(data.readings);
    } catch (e) {
        console.error("Failed to load chart data", e);
    }
}

function renderChart(readings) {
    if (!window.Chart) return; // Wait for CDN
    
    const ctx = els.chartCanvas.getContext('2d');
    
    if (currentChart) {
        currentChart.destroy();
    }
    
    // Sort chronological for chart
    const sorted = [...readings].reverse();
    
    const labels = sorted.map(r => {
        const d = new Date(r.recorded_at + "Z"); // SQLite timestamp is UTC
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    
    const moistureData = sorted.map(r => Math.round((r.soil_moisture / 1023) * 100));
    const waterData = sorted.map(r => Math.round((r.water_depth / 100) * 100));
    
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Soil Moisture %',
                    data: moistureData,
                    borderColor: '#4ade80',
                    backgroundColor: 'rgba(74, 222, 128, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0
                },
                {
                    label: 'Water Depth %',
                    data: waterData,
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: '#94a3b8' }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: { color: '#64748b', maxTicksLimit: 8 }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: { color: '#64748b' }
                }
            }
        }
    });
}

function appendDataToChart(data) {
    if (!currentChart) return;
    
    const d = new Date(data.timestamp * 1000);
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    currentChart.data.labels.push(timeStr);
    currentChart.data.datasets[0].data.push(data.soil_moisture_pct);
    currentChart.data.datasets[1].data.push(data.water_depth_pct);
    
    // Remove oldest if we have a lot
    if (currentChart.data.labels.length > 100) {
        currentChart.data.labels.shift();
        currentChart.data.datasets[0].data.shift();
        currentChart.data.datasets[1].data.shift();
    }
    
    currentChart.update('none'); // Update without full animation
}

// ─── Add Plant Modal ───────────────────────────────────────────────
function showAddModal() {
    els.addForm.reset();
    els.imagePreview.style.display = 'none';
    els.imagePreview.src = '';
    els.uploadPlaceholder.style.display = 'flex';
    els.bleScanResults.style.display = 'none';
    els.addModal.style.display = 'flex';
}

function hideAddModal() {
    els.addModal.style.display = 'none';
}

function handleImageSelect() {
    if (els.imageInput.files && els.imageInput.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
            els.imagePreview.src = e.target.result;
            els.imagePreview.style.display = 'block';
            els.uploadPlaceholder.style.display = 'none';
        };
        reader.readAsDataURL(els.imageInput.files[0]);
    }
}

async function handleBleScan(inputId, resultsId, btnEl) {
    btnEl.textContent = "Scanning...";
    btnEl.disabled = true;
    const resultsEl = document.getElementById(resultsId);
    const inputEl = document.getElementById(inputId);
    
    resultsEl.innerHTML = '';
    resultsEl.style.display = 'block';
    
    try {
        const res = await fetch('/api/ble/scan');
        const data = await res.json();
        
        if (data.devices.length === 0) {
            resultsEl.innerHTML = '<div class="ble-scan-item"><span class="name text-muted">No WOP devices found</span></div>';
        } else {
            data.devices.forEach(d => {
                const item = document.createElement('div');
                item.className = `ble-scan-item is-wop`;
                item.innerHTML = `
                    <span class="name">${d.name} 🌿</span>
                    <span class="address">${d.address}</span>
                `;
                item.onclick = () => {
                    inputEl.value = d.address;
                    resultsEl.style.display = 'none';
                };
                resultsEl.appendChild(item);
            });
        }
    } catch (err) {
        resultsEl.innerHTML = '<div class="ble-scan-item"><span class="name text-danger">Scan failed</span></div>';
    } finally {
        btnEl.textContent = "📡 Scan";
        btnEl.disabled = false;
    }
}

async function handleAddPlantSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData();
    if (els.imageInput.files.length > 0) {
        formData.append('image', els.imageInput.files[0]);
    }
    
    const name = document.getElementById('plant-name').value;
    if (name) formData.append('name', name);
    
    const ble = document.getElementById('plant-ble-address').value;
    if (ble) formData.append('ble_address', ble);
    
    const btnSubmit = document.getElementById('btn-submit-plant');
    const spinner = document.getElementById('submit-spinner');
    
    btnSubmit.disabled = true;
    spinner.style.display = 'inline-block';
    
    try {
        const res = await fetch('/api/plants', {
            method: 'POST',
            body: formData
        });
        
        if (res.ok) {
            hideAddModal();
            fetchPlants();
        } else {
            const err = await res.json();
            alert(`Error adding plant: ${err.detail || 'Unknown error'}`);
        }
    } catch (err) {
        alert("Failed to connect to server");
        console.error(err);
    } finally {
        btnSubmit.disabled = false;
        spinner.style.display = 'none';
    }
}

// ─── Edit Plant Modal ──────────────────────────────────────────────
function showEditModal() {
    if (!currentPlant) return;
    
    document.getElementById('edit-plant-id').value = currentPlant.id;
    document.getElementById('edit-name').value = currentPlant.name || '';
    document.getElementById('edit-species').value = currentPlant.species || '';
    document.getElementById('edit-moisture-min').value = currentPlant.ideal_moisture_min || 30;
    document.getElementById('edit-moisture-max').value = currentPlant.ideal_moisture_max || 70;
    document.getElementById('edit-light').value = currentPlant.light_preference || '';
    document.getElementById('edit-watering').value = currentPlant.watering_frequency || '';
    document.getElementById('edit-ble').value = currentPlant.ble_address || '';
    document.getElementById('edit-notes').value = currentPlant.notes || '';
    
    document.getElementById('ble-scan-results-edit').style.display = 'none';
    
    document.getElementById('edit-plant-modal').style.display = 'flex';
}

function hideEditModal() {
    document.getElementById('edit-plant-modal').style.display = 'none';
}

async function handleEditPlantSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('edit-plant-id').value;
    const payload = {
        name: document.getElementById('edit-name').value,
        species: document.getElementById('edit-species').value,
        ideal_moisture_min: parseInt(document.getElementById('edit-moisture-min').value),
        ideal_moisture_max: parseInt(document.getElementById('edit-moisture-max').value),
        light_preference: document.getElementById('edit-light').value,
        watering_frequency: document.getElementById('edit-watering').value,
        ble_address: document.getElementById('edit-ble').value,
        notes: document.getElementById('edit-notes').value
    };
    
    try {
        const res = await fetch(`/api/plants/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            hideEditModal();
            // Refresh detail view
            openPlantDetail(id);
        } else {
            const err = await res.json();
            alert(`Error updating plant: ${err.detail || 'Unknown error'}`);
        }
    } catch (err) {
        alert("Failed to connect to server");
        console.error(err);
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);
