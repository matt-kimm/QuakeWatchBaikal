import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // Разрешает передачу HttpOnly cookies
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient
