import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<any | null>(null)
  const isInitialized = ref(false)

  const isAuthenticated = computed(() => !!user.value)

  async function login(username: string, password: string) {
    const response = await apiClient.post('/auth/login', { username, password })
    user.value = response.data.user
  }

  async function register(username: string, password: string) {
    const response = await apiClient.post('/auth/register', { username, password })
    return response.data
  }

  async function logout() {
    try {
      await apiClient.post('/auth/logout')
    } finally {
      user.value = null
    }
  }

  async function checkAuth() {
    try {
      const response = await apiClient.get('/auth/me')
      user.value = response.data
    } catch {
      user.value = null
    } finally {
      isInitialized.value = true
    }
  }

  return {
    user,
    isAuthenticated,
    isInitialized,
    login,
    register,
    logout,
    checkAuth,
  }
})
