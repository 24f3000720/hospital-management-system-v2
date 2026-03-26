import { apiRequest } from './apiClient'

export function getDoctorProfile() {
  return apiRequest('/api/doctor/profile')
}

export function updateDoctorProfile(payload) {
  return apiRequest('/api/doctor/profile', {
    method: 'PUT',
    data: payload,
  })
}

export function getDoctorAppointments(status = '') {
  const query = new URLSearchParams()
  if (status) query.set('status', status)
  return apiRequest(`/api/doctor/appointments${query.toString() ? `?${query.toString()}` : ''}`)
}

export function completeDoctorAppointment(aid, payload) {
  return apiRequest(`/api/doctor/appointments/${aid}/complete`, {
    method: 'PUT',
    data: payload,
  })
}

export function updateDoctorAppointment(aid, payload) {
  return apiRequest(`/api/doctor/appointments/${aid}`, {
    method: 'PUT',
    data: payload,
  })
}

export function cancelDoctorAppointment(aid) {
  return apiRequest(`/api/doctor/appointments/${aid}/cancel`, {
    method: 'POST',
  })
}

export function getDoctorAvailability() {
  return apiRequest('/api/doctor/availability')
}

export function updateDoctorAvailability(payload) {
  return apiRequest('/api/doctor/availability', {
    method: 'PUT',
    data: payload,
  })
}

export function getDoctorPatientHistory(patientUid) {
  return apiRequest(`/api/doctor/patients/${patientUid}/history`)
}

export function sendDoctorMonthlyReportNow() {
  return apiRequest('/api/doctor/jobs/monthly-report/send-now', {
    method: 'POST',
  })
}
