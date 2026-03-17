import { apiRequest } from './apiClient'

export function login(credentials) {
  return apiRequest('/api/auth/login', {
    method: 'POST',
    data: credentials,
  })
}

export function register(payload) {
  return apiRequest('/api/auth/register', {
    method: 'POST',
    data: payload,
  })
}

export function logout() {
  return apiRequest('/api/auth/logout', {
    method: 'POST',
  })
}

export function fetchCurrentUser() {
  return apiRequest('/api/auth/me')
}
