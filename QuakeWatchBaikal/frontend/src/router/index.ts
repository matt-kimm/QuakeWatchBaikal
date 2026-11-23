import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // При первом открытии или перезагрузке страницы проверяем куку через бэкенд
  if (!auth.isInitialized) {
    await auth.checkAuth();
  }

  // Если маршрут защищен, а пользователь не авторизован — отправляем на логин
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return '/login';
  }

  // Если пользователь уже вошел и пытается открыть /login — возвращаем на главную
  if (to.name === 'login' && auth.isAuthenticated) {
    return '/';
  }
});

export default router;
