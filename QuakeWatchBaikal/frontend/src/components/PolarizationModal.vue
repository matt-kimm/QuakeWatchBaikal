<template>
  <el-dialog
    :model-value="!!seismicStore.selectedEarthquake"
    title="🔬 Поляризационный анализ сейсмических волн"
    width="92%"
    top="3vh"
    destroy-on-close
    @close="seismicStore.selectedEarthquake = null"
  >
    <div v-if="seismicStore.selectedEarthquake" class="analysis-wrapper">
      <!-- Панель параметров -->
      <el-form :inline="true" class="params-bar">
        <el-form-item label="Событие:">
          <el-tag type="danger" effect="dark">
            {{ seismicStore.selectedEarthquake.datetime_utc }} (K={{ seismicStore.selectedEarthquake.energy_class }})
          </el-tag>
        </el-form-item>

        <el-form-item label="Станция:">
          <el-select v-model="station" style="width: 190px">
            <el-option label="KYD (Култук / Кырен)" value="KYD" />
            <el-option label="ZUNM (Зун-Мурино)" value="ZUNM" />
          </el-select>
        </el-form-item>

        <el-form-item label="Дней до:">
          <el-input-number v-model="daysBefore" :min="1" :max="60" style="width: 110px" />
        </el-form-item>

        <el-form-item label="Дней после:">
          <el-input-number v-model="daysAfter" :min="0" :max="60" style="width: 110px" />
        </el-form-item>

        <el-form-item label="Примечание:">
          <el-input v-model="noteStr" placeholder="Опционально для графика" style="width: 200px" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="seismicStore.analysisLoading" @click="calculate">
            ▶ Рассчитать поляризацию
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />


      <!-- Основная рабочая область: Графики Plotly + Нодальные плоскости -->
      <div v-if="seismicStore.polarizationData && !errorMessage" v-loading="seismicStore.analysisLoading" class="results-grid">
        <div ref="plotlyContainer" class="plotly-box"></div>

        <div v-if="seismicStore.polarizationData" class="side-stats">
          <el-card shadow="never" class="stat-card">
            <template #header><b>📊 Статистика периодов</b></template>
            <p>
              <b>Фоновый период:</b><br />
              <span v-if="seismicStore.polarizationData.stats.bg_az !== null">
                Азимут: {{ seismicStore.polarizationData.stats.bg_az }}°, Угол выхода:
                {{ seismicStore.polarizationData.stats.bg_inc }}°
              </span>
              <span v-else class="muted">Недостаточно данных</span>
            </p>
            <p>
              <b>Подготовка (до 3 дней):</b><br />
              <span v-if="seismicStore.polarizationData.stats.pre_az !== null">
                Азимут: {{ seismicStore.polarizationData.stats.pre_az }}°, Угол выхода:
                {{ seismicStore.polarizationData.stats.pre_inc }}°
              </span>
              <span v-else class="muted">Недостаточно данных</span>
            </p>
            <p v-if="seismicStore.polarizationData.stats.diff_az !== null">
              <b>Разница азимута:</b>
              <el-tag size="small" type="info">{{ seismicStore.polarizationData.stats.diff_az }}°</el-tag>
            </p>
          </el-card>

          <el-card shadow="never" class="stat-card" style="margin-top: 12px">
            <template #header><b>🌐 Нодальные плоскости</b></template>
            <div class="ray-info">
              Азимут луча: <b>{{ seismicStore.polarizationData.ray_params.azimuth }}°</b> | Угол выхода:
              <b>{{ seismicStore.polarizationData.ray_params.incidence }}°</b>
            </div>
            <img
              v-if="seismicStore.polarizationData.beachball_png"
              :src="'data:image/png;base64,' + seismicStore.polarizationData.beachball_png"
              alt="Нодальные плоскости"
              class="beachball-img"
            />
          </el-card>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import Plotly from 'plotly.js-dist-min';
import { ElMessage } from 'element-plus';
import { useSeismicStore } from '@/stores/seismic';

const seismicStore = useSeismicStore();
const plotlyContainer = ref<HTMLElement | null>(null);
const errorMessage = ref<string | null>(null);

const station = ref('KYD');
const daysBefore = ref(1);
const daysAfter = ref(1);
const noteStr = ref('');

watch(
  () => seismicStore.selectedEarthquake,
  (eq) => {
    if (eq) {
      calculate();
    }
  }
);

async function calculate() {
  errorMessage.value = null;
  seismicStore.polarizationData = null;
  try {
    await seismicStore.runPolarizationAnalysis(station.value, daysBefore.value, daysAfter.value);
    await nextTick();
    renderPlotly();
  } catch (err: any) {
    errorMessage.value = err?.response?.data?.detail || 'Файлы сейсмограмм для выбранной даты и станции не найдены';
  }
}


function renderPlotly() {
  const res = seismicStore.polarizationData;
  if (!res || !plotlyContainer.value) return;

  const traces: Plotly.Data[] = [
    {
      x: res.timeline,
      y: res.azimuth,
      mode: 'markers',
      marker: { size: 4, color: 'blue' },
      name: 'Азимут',
      xaxis: 'x',
      yaxis: 'y',
    },
    {
      x: res.timeline,
      y: res.incidence_angle,
      mode: 'markers',
      marker: { size: 4, color: 'darkorange' },
      name: 'Угол выхода',
      xaxis: 'x',
      yaxis: 'y2',
    },
    {
      x: res.timeline,
      y: res.rectilinearity,
      mode: 'lines',
      line: { color: 'blue', width: 1.5 },
      name: 'Прямолинейность',
      xaxis: 'x',
      yaxis: 'y3',
    },
    {
      x: res.timeline,
      y: res.ellipticity,
      mode: 'lines',
      line: { color: 'darkorange', width: 1.5 },
      name: 'Эллиптичность',
      xaxis: 'x',
      yaxis: 'y3',
    },
    {
      x: res.timeline,
      y: res.tides,
      mode: 'lines',
      line: { color: 'grey', width: 2, dash: 'dot' },
      name: 'Прилив',
      xaxis: 'x',
      yaxis: 'y4',
    },
  ];

  const layout: Partial<Plotly.Layout> = {
    title: {
      text: `Станция: ${res.station}, Событие: ${res.eq_time}`,
      x: 0.01,
      xanchor: 'left',
    },
    height: 640,
    hovermode: 'x unified',
    legend: { orientation: 'h', y: 1.07, x: 1, xanchor: 'right' },
    margin: { t: 80, b: noteStr.value ? 80 : 50, l: 60, r: 60 },
    grid: { rows: 3, columns: 1, pattern: 'coupled', roworder: 'top to bottom' },
    xaxis: { title: 'Время (UTC)', tickformat: '%Y-%m-%d %H:%M' },
    yaxis: { range: new Array(0, 360), title: 'Азимут (°)', domain: [0.7, 1.0] },
    yaxis2: { range: new Array(0, 90), title: 'Угол выхода (°)', domain: [0.36, 0.66] },
    yaxis3: { range: new Array(0, 1), dtick: 0.2, title: 'Метрики формы', domain: [0.0, 0.32] },


    yaxis4: {
      title: 'Прилив (отн. ед.)',
      overlaying: 'y3',
      side: 'right',
      showgrid: false,
    },
    shapes: [
      {
        type: 'line',
        x0: res.eq_time,
        x1: res.eq_time,
        y0: 0,
        y1: 1,
        xref: 'x',
        yref: 'paper',
        line: { color: 'red', width: 2, dash: 'dash' },
      },
    ],
    annotations: noteStr.value
      ? [
          {
            text: `<b>Примечание:</b> ${noteStr.value}`,
            showarrow: false,
            xref: 'paper',
            yref: 'paper',
            x: 0,
            y: -0.11,
            xanchor: 'left',
            font: { size: 13 },
          },
        ]
      : [],
  };

  Plotly.newPlot(plotlyContainer.value, traces, layout, { responsive: true });
}
</script>

<style scoped>
.params-bar {
  background: #f5f7fa;
  padding: 12px 16px 0;
  border-radius: 6px;
  margin-bottom: 14px;
}
.results-grid {
  display: flex;
  gap: 16px;
  min-height: 640px;
}
.plotly-box {
  flex: 1;
  min-width: 0;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.side-stats {
  width: 310px;
  flex-shrink: 0;
}
.stat-card p {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.5;
}
.muted {
  color: #909399;
}
.ray-info {
  font-size: 12px;
  margin-bottom: 8px;
  text-align: center;
}
.beachball-img {
  width: 100%;
  height: auto;
  display: block;
}
</style>
