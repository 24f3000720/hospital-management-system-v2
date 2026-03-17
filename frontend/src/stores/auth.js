import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authService from '../services/authService'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const initialized = ref(false)
  const loading = ref(false)

  const isAuthenticated = computed(() => Boolean(user.value))
  const roleId = computed(() => user.value?.role_id ?? null)

  async function initialize() {
    if (initialized.value) return

    try {
      const response = await authService.fetchCurrentUser()
      user.value = response.data.user
    } catch {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function refreshUser() {
    const response = await authService.fetchCurrentUser()
    user.value = response.data.user
    initialized.value = true
    return user.value
  }

  async function login(credentials) {
    loading.value = true
    try {
      const response = await authService.login(credentials)
      user.value = response.data.user
      initialized.value = true
      return response.data.user
    } finally {
      loading.value = false
    }
  }

  async function register(payload) {
    loading.value = true
    try {
      return await authService.register(payload)
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    loading.value = true
    try {
      await authService.logout()
      user.value = null
      initialized.value = true
    } finally {
      loading.value = false
    }
  }

  return {
    user,
    initialized,
    loading,
    isAuthenticated,
    roleId,
    initialize,
    refreshUser,
    login,
    register,
    logout,
  }
})
