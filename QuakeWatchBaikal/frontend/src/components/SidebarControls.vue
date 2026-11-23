<template>
  <aside class="sidebar">
    <div class="header">
      <h2>QuakeWatchBaikal</h2>
    </div>

    <div class="section">
      <h4>1. Загрузка каталогов с ПК (.csv)</h4>

      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".csv"
        :on-change="(f: any) => (eqFile = f.raw)"
        :on-remove="() => (eqFile = null)"
      >
        <el-button size="small" plain style="width: 295px">
          📄 Выбрать каталог землетрясений (CSV)
        </el-button>
      </el-upload>

      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".geojson,.json,.csv"
        style="margin-top: 8px"
        :on-change="(f: any) => (faultFile = f.raw)"
        :on-remove="() => (faultFile = null)"
      >
        <el-button size="small" plain style="width: 295px">
          🗺️ Выбрать каталог разломов (GeoJSON)
        </el-button>
      </el-upload>


      <el-button
        type="warning"
        :loading="seismicStore.initLoading"
        :disabled="!eqFile && !faultFile"
        style="width: 100%; margin-top: 10px"
        @click="handleUpload"
      >
        ⬆️ Загрузить файлы в БД
      </el-button>

      <el-button
        type="primary"
        :loading="seismicStore.loading"
        style="width: 100%; margin-left: 0; margin-top: 10px"
        @click="handleLoadMap"
      >
        🔄 Отобразить данные на карте
      </el-button>
    </div>

    <el-divider />

    <div class="section">
      <h4>2. Интервал времени и класс (К)</h4>
      <el-form label-position="top">
        <el-form-item label="Начало интервала">
          <el-date-picker
            v-model="seismicStore.filters.start_date"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="Конец интервала">
          <el-date-picker
            v-model="seismicStore.filters.end_date"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="Минимальный энерг. класс (К)">
          <el-input-number
            v-model="seismicStore.filters.min_energy_class"
            :step="0.5"
            :min="0"
            :max="20"
            style="width: 100%"
          />
        </el-form-item>

        <el-button
          type="success"
          :loading="seismicStore.loading"
          style="width: 100%"
          @click="handleLoadMap"
        >
          Применить фильтры
        </el-button>

        <el-divider />
        <div class="section">
          <h4>3. Сейсмо-метеоанализ (MT)</h4>
          <el-button type="info" plain style="width: 100%" @click="meteoVisible = true">
            🌤️ Спектрограмма и ветер (MT)
          </el-button>
        </div>
        <MeteoAnalysisModal v-model:visible="meteoVisible" />

      </el-form>
    </div>

    <div class="footer">
      <el-button type="danger" plain style="width: 100%" @click="handleLogout">
        Выйти из системы
      </el-button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useSeismicStore } from '@/stores/seismic';
import { useAuthStore } from '@/stores/auth';
import MeteoAnalysisModal from '@/components/MeteoAnalysisModal.vue';

const seismicStore = useSeismicStore();
const authStore = useAuthStore();
const router = useRouter();

const eqFile = ref<File | null>(null);
const faultFile = ref<File | null>(null);
const meteoVisible = ref(false);

async function handleUpload() {
  try {
    const res = await seismicStore.uploadCatalogs(eqFile.value, faultFile.value);
    ElMessage.success(res.message);
    await handleLoadMap();
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'Ошибка при загрузке CSV-файлов');
  }
}

async function handleLoadMap() {
  try {
    await seismicStore.fetchEarthquakes();
    if (seismicStore.earthquakes.length === 0) {
      ElMessage.warning('За выбранный интервал событий не найдено (проверьте даты или загрузите CSV)');
    } else {
      ElMessage.success(`На карте отображено событий: ${seismicStore.earthquakes.length}`);
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'Ошибка получения данных с сервера');
  }
}

function handleLogout() {
  authStore.logout();
  router.push('/login');
}
</script>

<style scoped>
.sidebar {
  width: 340px;
  height: 100vh;
  padding: 20px;
  background: #ffffff;
  border-right: 1px solid #dcdfe6;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow-y: auto;
}
.footer {
  margin-top: auto;
  padding-top: 20px;
}
</style>
