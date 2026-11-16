<template>
  <el-dialog
    :model-value="visible"
    title="🌤️ Сейсмо-метеорологический анализ (Спектрограмма + Ветер MT)"
    width="92%"
    top="3vh"
    destroy-on-close
    @close="$emit('update:visible', false)"
  >
    <div v-loading="loading">
      <el-form :inline="true" class="params-bar">
        <el-form-item label="Начало:">
          <el-date-picker
            v-model="startTime"
            type="datetime"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 195px"
          />
        </el-form-item>

        <el-form-item label="Конец:">
          <el-date-picker
            v-model="endTime"
            type="datetime"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 195px"
          />
        </el-form-item>

        <el-form-item label="Сейсмостанция:">
          <el-select v-model="station" style="width: 110px">
            <el-option label="KYD" value="KYD" />
            <el-option label="ZUNM" value="ZUNM" />
          </el-select>
        </el-form-item>

        <el-form-item label="Канал:">
          <el-select v-model="channel" style="width: 110px">
            <el-option label="0 (E)" :value="0" />
            <el-option label="1 (N)" :value="1" />
            <el-option label="2 (Z)" :value="2" />
          </el-select>
        </el-form-item>

        <el-form-item label="Метеостанция:">
          <el-input v-model="mtStation" style="width: 100px" />
        </el-form-item>

        <el-form-item label="Частоты (Гц):">
          <el-input-number v-model="f1" :min="0.1" :max="40" :step="0.5" style="width: 95px" />
          <span style="margin: 0 6px">—</span>
          <el-input-number v-model="f2" :min="0.5" :max="50" :step="0.5" style="width: 95px" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runAnalysis">
            ▶ Построить графики
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="errorMsg"
        :title="errorMsg"
        type="error"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />

      <div v-if="resultData && !errorMsg" class="result-area">
        <div class="summary-bar">
          <el-tag type="info">Сейсмоканал: <b>{{ resultData.station }}</b></el-tag>
          <el-tag type="warning">Средний ветер: <b>{{ resultData.mean_wind_speed }} м/с</b></el-tag>
          <el-tag type="danger">Макс. порыв ветра: <b>{{ resultData.max_wind_speed }} м/с</b></el-tag>
        </div>
        <div class="plot-container">
          <img :src="'data:image/png;base64,' + resultData.plot_png" alt="Сейсмо-метеорологический график" />
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { apiClient } from '@/api/client';

defineProps<{ visible: boolean }>();
defineEmits(['update:visible']);

const startTime = ref('2023-03-20T12:00:00');
const endTime = ref('2023-03-21T12:00:00');
const station = ref('KYD');
const channel = ref(2);
const mtStation = ref('bugd');
const f1 = ref(1.0);
const f2 = ref(5.0);

const loading = ref(false);
const errorMsg = ref<string | null>(null);
const resultData = ref<any>(null);

async function runAnalysis() {
  loading.value = true;
  errorMsg.value = null;
  resultData.value = null;
  try {
    const { data } = await apiClient.get('/analysis/meteo-seismic', {
      params: {
        start_time: startTime.value,
        end_time: endTime.value,
        station: station.value,
        channel: channel.value,
        mt_station: mtStation.value,
        f1: f1.value,
        f2: f2.value,
      },
    });
    resultData.value = data;
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || 'Ошибка при расчете метео-сейсмических данных';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.params-bar {
  background: #f5f7fa;
  padding: 12px 16px 0;
  border-radius: 6px;
  margin-bottom: 14px;
}
.summary-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.plot-container {
  text-align: center;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px;
  background: #fff;
  overflow-x: auto;
}
.plot-container img {
  max-width: 100%;
  height: auto;
}
</style>
