import { apiRequest } from './apiClient'

export function getDepartments() {
  return apiRequest('/api/departments')
}

export function searchDoctors({ search = '', specialization = '', department = '', availableOn = '' } = {}) {
  const query = new URLSearchParams()
  if (search) query.set('search', search)
  if (specialization) query.set('specialization', specialization)
  if (department) query.set('department', department)
  if (availableOn) query.set('available_on', availableOn)
  return apiRequest(`/api/doctors${query.toString() ? `?${query.toString()}` : ''}`)
}

export function getDoctorBookingSlots(uid) {
  return apiRequest(`/api/patient/doctors/${uid}/slots`)
}

export function getPatientProfile() {
  return apiRequest('/api/patient/profile')
}

export function updatePatientProfile(payload) {
  return apiRequest('/api/patient/profile', {
    method: 'PUT',
    data: payload,
  })
}

export function getPatientAppointments() {
  return apiRequest('/api/patient/appointments')
}

export function bookAppointment(payload) {
  return apiRequest('/api/patient/appointments', {
    method: 'POST',
    data: payload,
  })
}

export function cancelPatientAppointment(aid) {
  return apiRequest(`/api/patient/appointments/${aid}/cancel`, {
    method: 'POST',
  })
}

export function reschedulePatientAppointment(aid, payload) {
  return apiRequest(`/api/patient/appointments/${aid}/reschedule`, {
    method: 'PUT',
    data: payload,
  })
}

export function getPatientExports() {
  return apiRequest('/api/patient/exports')
}

export function createTreatmentExport() {
  return apiRequest('/api/patient/exports/treatments', {
    method: 'POST',
  })
}

export function sendPatientReminderNow() {
  return apiRequest('/api/patient/jobs/daily-reminder/send-now', {
    method: 'POST',
  })
}

export function sendPatientExportAlertNow() {
  return apiRequest('/api/patient/jobs/export-alert/send-now', {
    method: 'POST',
  })
}

export function getPatientPayments() {
  return apiRequest('/api/patient/payments')
}

export function createDummyPayment(payload) {
  return apiRequest('/api/patient/payments', {
    method: 'POST',
    data: payload,
  })
}
