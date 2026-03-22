import { apiRequest } from './apiClient'

export function getAdminStats() {
  return apiRequest('/api/admin/stats')
}

export function getAdminAnalytics() {
  return apiRequest('/api/admin/analytics')
}

export function getAdminDoctors(search = '') {
  const query = new URLSearchParams()
  if (search) query.set('search', search)
  return apiRequest(`/api/admin/doctors${query.toString() ? `?${query.toString()}` : ''}`)
}

export function createDoctor(payload) {
  return apiRequest('/api/admin/doctors', {
    method: 'POST',
    data: payload,
  })
}

export function getAdminPatients(search = '') {
  const query = new URLSearchParams()
  if (search) query.set('search', search)
  return apiRequest(`/api/admin/patients${query.toString() ? `?${query.toString()}` : ''}`)
}

export function getAdminUserDetail(uid) {
  return apiRequest(`/api/admin/users/${uid}`)
}

export function updateAdminUser(uid, payload) {
  return apiRequest(`/api/admin/users/${uid}`, {
    method: 'PUT',
    data: payload,
  })
}

export function updateAdminUserBlacklist(uid, blacklisted) {
  return apiRequest(`/api/admin/users/${uid}/blacklist`, {
    method: 'PUT',
    data: { blacklisted },
  })
}

export function getAdminAppointments({ search = '', apptTab = '' } = {}) {
  const query = new URLSearchParams()
  if (search) query.set('search', search)
  if (apptTab) query.set('appt_tab', apptTab)
  return apiRequest(`/api/admin/appointments${query.toString() ? `?${query.toString()}` : ''}`)
}

export function getAdminAppointmentDetail(aid) {
  return apiRequest(`/api/admin/appointments/${aid}`)
}

export function updateAdminAppointment(aid, payload) {
  return apiRequest(`/api/admin/appointments/${aid}`, {
    method: 'PUT',
    data: payload,
  })
}
