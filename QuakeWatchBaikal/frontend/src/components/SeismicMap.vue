<template>
  <div ref="mapContainer" class="map-container"></div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useSeismicStore } from '@/stores/seismic';

const mapContainer = ref<HTMLElement | null>(null);
const seismicStore = useSeismicStore();
let map: L.Map | null = null;
let markersLayer: L.LayerGroup | null = null;
let faultsLayer: L.LayerGroup | null = null;

onMounted(() => {
  if (!mapContainer.value) return;

  map = L.map(mapContainer.value).setView([53.5, 108.0], 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  faultsLayer = L.layerGroup().addTo(map);
  markersLayer = L.layerGroup().addTo(map);
  renderAll();
});

watch(
  () => [seismicStore.earthquakes, seismicStore.faults],
  () => renderAll(),
  { deep: true }
);

function renderAll() {
  renderFaults();
  renderMarkers();
}

function renderFaults() {
  if (!faultsLayer) return;
  faultsLayer.clearLayers();

  seismicStore.faults.forEach((fault) => {
    const isHigh =
      fault.fault_type.toLowerCase().includes('высокая') ||
      fault.fault_type.toLowerCase().includes('повышенная');

    const line = L.polyline(fault.coordinates, {
      color: isHigh ? '#8b0000' : '#d97706',
      weight: isHigh ? 3 : 2,
      opacity: 0.85,
    });

    line.bindPopup(`
      <div style="font-size: 13px; line-height: 1.5;">
        <b>Разлом:</b> ${fault.name}<br/>
        <b>Характеристики:</b> ${fault.fault_type}
      </div>
    `);

    line.addTo(faultsLayer!);
  });
}

function renderMarkers() {
  if (!markersLayer) return;
  markersLayer.clearLayers();

  seismicStore.earthquakes.forEach((eq) => {
    const radius = Math.max(5, (eq.energy_class - 6) * 2.2);
    const marker = L.circleMarker([eq.latitude, eq.longitude], {
      radius,
      color: '#b91c1c',
      fillColor: '#ef4444',
      fillOpacity: 0.75,
      weight: 1.5,
    });

    const popupEl = document.createElement('div');
    popupEl.innerHTML = `
      <div style="font-size: 13px; line-height: 1.5;">
        <b>Дата (UTC):</b> ${eq.datetime_utc}<br/>
        <b>Координаты:</b> ${eq.latitude}, ${eq.longitude}<br/>
        <b>Класс (K):</b> ${eq.energy_class}<br/>
        <button id="analyze-btn-${eq.id}" style="
          margin-top: 8px; width: 100%; padding: 6px 10px;
          background: #409eff; color: white; border: none;
          border-radius: 4px; cursor: pointer; font-weight: bold;">
          🔬 Поляризационный анализ
        </button>
      </div>
    `;

    marker.bindPopup(popupEl);
    marker.on('popupopen', () => {
      const btn = document.getElementById(`analyze-btn-${eq.id}`);
      if (btn) {
        btn.onclick = () => {
          marker.closePopup();
          seismicStore.openAnalysis(eq);
        };
      }
    });

    marker.addTo(markersLayer!);
  });
}
</script>

<style scoped>
.map-container {
  flex: 1;
  height: 100vh;
}
</style>
