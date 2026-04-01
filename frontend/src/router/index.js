import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { pinia } from '../stores'
import AdminDashboardView from '../views/AdminDashboardView.vue'
import CreateDoctorView from '../views/CreateDoctorView.vue'
import DoctorDashboardView from '../views/DoctorDashboardView.vue'
import LandingView from '../views/LandingView.vue'
import LoginView from '../views/LoginView.vue'
import PatientDashboardView from '../views/PatientDashboardView.vue'
import PatientPaymentsView from '../views/PatientPaymentsView.vue'
import RegisterView from '../views/RegisterView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'landing', component: LandingView },
    { path: '/signin', name: 'signin', component: LoginView },
    { path: '/signup', name: 'signup', component: RegisterView },
    { path: '/admin', name: 'admin', component: AdminDashboardView, meta: { requiresAuth: true, roleId: 1 } },
    { path: '/admin/create-doctor', name: 'create-doctor', component: CreateDoctorView, meta: { requiresAuth: true, roleId: 1 } },
    { path: '/patient', name: 'patient', component: PatientDashboardView, meta: { requiresAuth: true, roleId: 2 } },
    { path: '/patient/payments', name: 'patient-payments', component: PatientPaymentsView, meta: { requiresAuth: true, roleId: 2 } },
    { path: '/doctor', name: 'doctor', component: DoctorDashboardView, meta: { requiresAuth: true, roleId: 3 } },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)
  await authStore.initialize()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'signin' }
  }

  if (to.meta.roleId && authStore.roleId !== to.meta.roleId) {
    if (authStore.roleId === 1) return { name: 'admin' }
    if (authStore.roleId === 2) return { name: 'patient' }
    if (authStore.roleId === 3) return { name: 'doctor' }
    return { name: 'signin' }
  }

  if ((to.name === 'signin' || to.name === 'signup') && authStore.isAuthenticated) {
    if (authStore.roleId === 1) return { name: 'admin' }
    if (authStore.roleId === 2) return { name: 'patient' }
    if (authStore.roleId === 3) return { name: 'doctor' }
  }

  return true
})

export default router
