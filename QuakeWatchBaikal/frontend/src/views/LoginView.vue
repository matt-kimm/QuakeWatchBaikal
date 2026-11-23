<!-- src/views/LoginView.vue -->
<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5">
    <el-card style="width: 380px">
      <h3>Вход в QuakeWatchBaikal</h3>
      <el-form @submit.prevent="onLogin">
        <el-form-item><el-input v-model="username" placeholder="Логин" /></el-form-item>
        <el-form-item><el-input v-model="password" type="password" placeholder="Пароль" /></el-form-item>
        <el-button type="primary" native-type="submit" style="width: 100%">Войти</el-button>
        <el-button text style="width: 100%; margin-top: 8px" @click="onRegister">Зарегистрироваться</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '@/stores/auth';

const username = ref('');
const password = ref('');
const auth = useAuthStore();
const router = useRouter();

async function onLogin() {
  try {
    await auth.login(username.value, password.value);
    router.push('/');
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || 'Ошибка входа');
  }
}

async function onRegister() {
  try {
    await auth.register(username.value, password.value);
    ElMessage.success('Пользователь создан, теперь нажмите «Войти»');
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || 'Ошибка регистрации');
  }
}
</script>
