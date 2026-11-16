import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiClient } from '@/api/client';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'));
  const isAuthenticated = computed(() => !!token.value);

  async function login(username: string, password: string) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const { data } = await apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    token.value = data.access_token;
    localStorage.setItem('access_token', data.access_token);
  }

  async function register(username: string, email: string, password: string) {
    await apiClient.post('/auth/register', { username, email, password });
  }

  function logout() {
    token.value = null;
    localStorage.removeItem('access_token');
  }

  return { token, isAuthenticated, login, register, logout };
});
