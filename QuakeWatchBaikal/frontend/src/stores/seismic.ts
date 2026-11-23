import { defineStore } from 'pinia';
import { ref } from 'vue';
import { apiClient } from '@/api/client';
import type { Earthquake, FilterParams, PolarizationResult } from '@/types/seismic';

export interface FaultLine {
  id: number;
  name: string;
  fault_type: string;
  coordinates: [number, number][];
}

export const useSeismicStore = defineStore('seismic', () => {
  const earthquakes = ref<Earthquake[]>([]);
  const faults = ref<FaultLine[]>([]);
  const loading = ref(false);
  const initLoading = ref(false);

  const selectedEarthquake = ref<Earthquake | null>(null);
  const analysisLoading = ref(false);
  const polarizationData = ref<PolarizationResult | null>(null);

  const filters = ref<FilterParams>({
    start_date: '2020-01-01T00:00',
    end_date: '2026-12-31T23:59',
    min_energy_class: 6.0,
  });

  async function uploadCatalogs(eqFile: File | null, faultFile: File | null) {
    initLoading.value = true;
    try {
      const formData = new FormData();
      if (eqFile) formData.append('earthquakes_file', eqFile);
      if (faultFile) formData.append('faults_file', faultFile);

      const { data } = await apiClient.post('/catalogs/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data;
    } finally {
      initLoading.value = false;
    }
  }

  async function fetchEarthquakes() {
    loading.value = true;
    try {
      const [eqRes, faultRes] = await Promise.all([
        apiClient.get<Earthquake[]>('/earthquakes', {
          params: {
            start_date: filters.value.start_date,
            end_date: filters.value.end_date,
            min_energy_class: filters.value.min_energy_class,
          },
        }),
        apiClient.get<FaultLine[]>('/faults'),
      ]);
      earthquakes.value = eqRes.data;
      faults.value = faultRes.data;
    } finally {
      loading.value = false;
    }
  }

  function openAnalysis(eq: Earthquake) {
    selectedEarthquake.value = eq;
    polarizationData.value = null;
  }

  async function runPolarizationAnalysis(station: string, daysBefore: number, daysAfter: number) {
    if (!selectedEarthquake.value) return;
    analysisLoading.value = true;
    try {
      const { data } = await apiClient.get<PolarizationResult>('/analysis/polarization', {
        params: {
          earthquake_id: selectedEarthquake.value.id,
          station,
          days_before: daysBefore,
          days_after: daysAfter,
        },
      });
      polarizationData.value = data;
    } finally {
      analysisLoading.value = false;
    }
  }

  return {
    earthquakes,
    faults,
    filters,
    loading,
    initLoading,
    selectedEarthquake,
    analysisLoading,
    polarizationData,
    uploadCatalogs,
    fetchEarthquakes,
    openAnalysis,
    runPolarizationAnalysis,
  };
});
