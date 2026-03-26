<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  cancelDoctorAppointment,
  completeDoctorAppointment,
  getDoctorAppointments,
  getDoctorAvailability,
  getDoctorProfile,
  sendDoctorMonthlyReportNow,
  updateDoctorAppointment,
  updateDoctorAvailability,
  updateDoctorProfile,
} from '../services/doctorService'
import { useAuthStore } from '../stores/auth'
import {
  buildDoctorCalendarData,
  getAppointmentHistoryDateTime,
  isAppointmentHistorical,
  normalizeAppointment,
  normalizeUser,
} from '../utils/dashboardData'

const router = useRouter()
const authStore = useAuthStore()

const state = reactive({
  currentUser: null,
  appointments: [],
  availability: [],
})

const selected_date = ref('')
const view_mode = ref('all')
const selected_appointment = ref(null)
const edit_profile = ref(false)
const sendingMonthlyReportNow = ref(false)
const historySaveTimers = new Map()

const profileForm = reactive({
  name: '',
  email: '',
  password: '',
  experience_years: '',
  specialization: '',
  dept: '',
  profile_image_data: '',
})

const calendarData = computed(() => buildDoctorCalendarData(state.appointments, state.availability, new Date()))

const jinjaemail = computed(() => state.currentUser?.email || '')
const current_user = computed(() => state.currentUser)
const total_appointments = computed(() => calendarData.value.allAppointments.length)
const calendar_days = computed(() => calendarData.value.calendarDays)
const all_appointments = computed(() => calendarData.value.allAppointments)

const selected_date_formatted = computed(() => {
  const day = calendar_days.value.find((entry) => entry.date === selected_date.value)
  if (!day) return selected_date.value
  if (day.formatted_date === 'Today' || day.formatted_date === 'Tomorrow') return day.formatted_date
  return `${day.formatted_date}, ${selected_date.value.slice(0, 4)}`
})

const day_slots = computed(() => calendarData.value.daySlotsByDate[selected_date.value] ?? [])
const monthlyReportNotice = computed(() => {
  const now = new Date()
  const isFirstDay = now.getDate() === 1

  if (isFirstDay) {
    return 'Monthly PDF + email report is scheduled to be sent today at 08:30 AM.'
  }

  return 'Monthly PDF + email report is sent on the 1st of each month at 08:30 AM.'
})

const automatic_patient_history = computed(() => {
  const now = new Date()
  const upcomingAppointments = state.appointments.filter(
    (appointment) =>
      appointment.status === 'scheduled' && new Date(appointment.appointment_datetime) >= now,
  )

  const seenPatients = new Set()
  const historyRows = []

  for (const appointment of upcomingAppointments) {
    const patientUid = appointment.patient?.uid
    if (!patientUid || seenPatients.has(patientUid)) continue
    seenPatients.add(patientUid)

    const latestPastAppointment = state.appointments
      .filter((item) => {
        if (item.patient?.uid !== patientUid) return false
        if (item.aid === appointment.aid) return false
        return isAppointmentHistorical(item, now)
      })
      .sort(
        (left, right) =>
          new Date(getAppointmentHistoryDateTime(right)) - new Date(getAppointmentHistoryDateTime(left)),
      )[0]

    if (latestPastAppointment) {
      historyRows.push({ ...latestPastAppointment })
    }
  }

  return historyRows
})

function syncProfileForm() {
  profileForm.name = state.currentUser?.name || ''
  profileForm.email = state.currentUser?.email || ''
  profileForm.password = ''
  profileForm.experience_years = state.currentUser?.experience_years ?? ''
  profileForm.specialization = state.currentUser?.specialization || ''
  profileForm.dept = state.currentUser?.department?.name || ''
  profileForm.profile_image_data = state.currentUser?.profile_image_data || ''
}

function replaceAppointment(updatedAppointment) {
  state.appointments = state.appointments.map((appointment) =>
    appointment.aid === updatedAppointment.aid ? updatedAppointment : appointment,
  )

  if (selected_appointment.value?.aid === updatedAppointment.aid) {
    selected_appointment.value = updatedAppointment
  }
}

async function loadDoctorProfile() {
  const response = await getDoctorProfile()
  state.currentUser = normalizeUser(response.data.doctor)
  syncProfileForm()
}

async function loadDoctorAppointments() {
  const response = await getDoctorAppointments()
  state.appointments = response.data.appointments.map(normalizeAppointment)
}

async function loadDoctorAvailability() {
  const response = await getDoctorAvailability()
  state.availability = response.data.availability
}

async function refreshDashboardData() {
  await Promise.all([loadDoctorAppointments(), loadDoctorAvailability()])

  if (!selected_date.value && calendar_days.value.length) {
    selected_date.value = calendar_days.value[0].date
  }
}

function showAllAppointments() {
  view_mode.value = 'all'
  selected_appointment.value = null
  edit_profile.value = false
}

function showDay(date) {
  selected_date.value = date
  view_mode.value = 'day'
  selected_appointment.value = null
  edit_profile.value = false
}

function openEditProfile() {
  edit_profile.value = true
  selected_appointment.value = null
}

function openAppointment(appointmentId) {
  selected_appointment.value =
    state.appointments.find((appointment) => appointment.aid === appointmentId) ?? null
  edit_profile.value = false
}

function closePanel() {
  edit_profile.value = false
  selected_appointment.value = null
}

function getProfileInitials(name) {
  return (name || 'Doctor')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || 'D'
}

function handleProfileImageChange(event) {
  const [file] = event.target.files || []
  if (!file) return

  if (!file.type.startsWith('image/')) {
    window.alert('Please choose an image file.')
    event.target.value = ''
    return
  }

  if (file.size > 700 * 1024) {
    window.alert('Please choose an image smaller than 700 KB.')
    event.target.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    profileForm.profile_image_data = typeof reader.result === 'string' ? reader.result : ''
  }
  reader.readAsDataURL(file)
  event.target.value = ''
}

function removeProfileImage() {
  profileForm.profile_image_data = ''
}

async function toggleAvailability(slot) {
  if (slot.booked) return

  try {
    await updateDoctorAvailability({
      slot_str: slot.slot_str,
      available: !slot.available,
    })
    await loadDoctorAvailability()
  } catch (error) {
    window.alert(error.message || 'Unable to update slot availability.')
  }
}

async function saveProfile() {
  if (!profileForm.name.trim() || !profileForm.email.trim()) {
    window.alert('Name and email are required.')
    return
  }

  if (profileForm.password && profileForm.password.length < 6) {
    window.alert('New password must be at least 6 characters long.')
    return
  }

  try {
    const response = await updateDoctorProfile({
      name: profileForm.name,
      email: profileForm.email,
      password: profileForm.password,
      experience_years: Number(profileForm.experience_years || 0),
      specialization: profileForm.specialization,
      dept: profileForm.dept,
      profile_image_data: profileForm.profile_image_data,
    })

    state.currentUser = normalizeUser(response.data.doctor)
    syncProfileForm()
    await authStore.refreshUser()
    window.alert('Profile updated successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to update profile.')
  }
}

async function saveAppointment() {
  if (!selected_appointment.value) return
  if (!selected_appointment.value.diagnosis?.trim() || !selected_appointment.value.prescription?.trim()) {
    window.alert('Diagnosis and prescription are required before completing an appointment.')
    return
  }

  try {
    const response = await completeDoctorAppointment(selected_appointment.value.aid, {
      diagnosis: selected_appointment.value.diagnosis || '',
      prescription: selected_appointment.value.prescription || '',
      doctor_notes: selected_appointment.value.doctor_notes || '',
    })

    replaceAppointment(normalizeAppointment(response.data.appointment))
    await refreshDashboardData()
    window.alert('Appointment marked as completed.')
  } catch (error) {
    window.alert(error.message || 'Unable to complete appointment.')
  }
}

async function persistHistoryAppointment(historyAppointment) {
  try {
    const response = await updateDoctorAppointment(historyAppointment.aid, {
      diagnosis: historyAppointment.diagnosis || '',
      prescription: historyAppointment.prescription || '',
      doctor_notes: historyAppointment.doctor_notes || '',
    })

    const updatedAppointment = normalizeAppointment(response.data.appointment)
    replaceAppointment(updatedAppointment)
  } catch (error) {
    window.alert(error.message || 'Unable to update patient history.')
  }
}

function scheduleHistoryAutosave(historyAppointment) {
  const existingTimer = historySaveTimers.get(historyAppointment.aid)
  if (existingTimer) {
    window.clearTimeout(existingTimer)
  }

  const timerId = window.setTimeout(async () => {
    historySaveTimers.delete(historyAppointment.aid)
    await persistHistoryAppointment(historyAppointment)
  }, 700)

  historySaveTimers.set(historyAppointment.aid, timerId)
}

function formatHistoryAppointment(dateTime) {
  const date = new Date(dateTime)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

async function cancelAppointment() {
  if (!selected_appointment.value) return

  try {
    const response = await cancelDoctorAppointment(selected_appointment.value.aid)
    replaceAppointment(normalizeAppointment(response.data.appointment))
    await refreshDashboardData()
    window.alert('Appointment cancelled successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to cancel appointment.')
  }
}

async function handleLogout() {
  await authStore.logout()
  await router.push({ name: 'signin' })
}

async function triggerMonthlyReportSendNow() {
  if (sendingMonthlyReportNow.value) return

  sendingMonthlyReportNow.value = true
  try {
    const response = await sendDoctorMonthlyReportNow()
    window.alert(response.message || 'Monthly report sent successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to send the monthly report right now.')
  } finally {
    sendingMonthlyReportNow.value = false
  }
}

onMounted(async () => {
  try {
    await authStore.initialize()
    await loadDoctorProfile()
    await refreshDashboardData()
  } catch (error) {
    window.alert(error.message || 'Unable to load the doctor dashboard.')
  }
})

onUnmounted(() => {
  for (const timerId of historySaveTimers.values()) {
    window.clearTimeout(timerId)
  }
  historySaveTimers.clear()
})
</script>

<template>
  <div class="container">
    <div class="left">
      <div>
        <div class="sidebar-header">Local Hospital Management System</div>
        <div class="sidebar-name">Welcome, {{ jinjaemail }}</div>
        <div class="sidebar-calendar">
          <a href="#" class="calendar-item" :class="{ selected: view_mode === 'all' }" @click.prevent="showAllAppointments">
            <span class="calendar-label">All Appointments</span>
            <span class="calendar-count">{{ total_appointments }}</span>
          </a>
          <a
            v-for="day in calendar_days"
            :key="day.date"
            href="#"
            class="calendar-item"
            :class="{ selected: day.date === selected_date && view_mode !== 'all' }"
            @click.prevent="showDay(day.date)"
          >
            <span class="calendar-label">{{ day.formatted_date }}</span>
            <span class="calendar-count">{{ day.appointment_count }}</span>
          </a>
        </div>
      </div>

      <a href="#" class="edit-profile-btn" @click.prevent="openEditProfile">Edit Profile</a>

      <a href="#" class="logout" @click.prevent="handleLogout">Logout</a>
    </div>
    <div class="divider"></div>

    <div class="right" :class="{ 'panel-open': selected_appointment || edit_profile }" id="main-content">
      <div class="dashboard-job-note">
        <p class="job-notice notice-inline">
          <span>{{ monthlyReportNotice }}</span>
          <button type="button" class="job-send-link" @click="triggerMonthlyReportSendNow">
            {{ sendingMonthlyReportNow ? 'Sending...' : 'Send Now' }}
          </button>
        </p>
      </div>
      <template v-if="view_mode === 'all' && automatic_patient_history.length">
        <div class="past-section doctor-history-section">
          <div class="past-appointment-card">
            <div v-for="appt in automatic_patient_history" :key="appt.aid" class="past-appointment-line doctor-history-line">
              <div class="past-appointment-info">
                <h4>Past appointment with {{ appt.patient_name }} on {{ formatHistoryAppointment(appt.history_datetime) }}</h4>
                <div class="history-edit-form">
                  <input v-model="appt.diagnosis" type="text" class="history-textfield" placeholder="Diagnosis" @input="scheduleHistoryAutosave(appt)">
                  <input v-model="appt.prescription" type="text" class="history-textfield" placeholder="Prescription" @input="scheduleHistoryAutosave(appt)">
                  <input v-model="appt.doctor_notes" type="text" class="history-textfield" placeholder="Doctor Notes" @input="scheduleHistoryAutosave(appt)">
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template v-if="view_mode === 'all'">
        <div class="all-appointments-section">
          <h3>All Appointments</h3>
          <template v-if="all_appointments.length">
            <div v-for="appt in all_appointments" :key="appt.aid" class="available-doctors">
              <div class="doctor-avatar"></div>
              <div class="doctor-info">
                <h4>{{ appt.patient_name }}</h4>
                <p class="doctor-dept">{{ appt.formatted_time }} - {{ appt.formatted_date }}</p>
              </div>
              <div class="doctor-actions">
                <a href="#" class="action-button" @click.prevent="openAppointment(appt.aid)">View Details</a>
              </div>
            </div>
          </template>
          <div v-else class="no-appointment-card">
            <p style="margin: 0; color: #686868;">No appointments scheduled yet.</p>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="day-slots-section">
          <h3>{{ selected_date_formatted }}</h3>
          <div class="slot-help-text">Tap on the appointment slots to toggle availability</div>
          <div class="slots-grid">
            <template v-for="slot in day_slots" :key="slot.slot_str">
              <a
                v-if="slot.booked"
                href="#"
                class="slot-card slot-booked"
                @click.prevent="openAppointment(slot.appointment_id)"
              >
                <div class="slot-content">
                  <div class="slot-header">Requested by {{ slot.patient_name }}</div>
                  <div class="slot-action-text">View Details</div>
                </div>
                <div class="slot-time">{{ slot.time_range }}</div>
              </a>
              <div v-else class="slot-card" :class="slot.available ? 'slot-available' : 'slot-unavailable'" style="position:relative;">
                <form class="availability-form" @submit.prevent="toggleAvailability(slot)">
                  <button type="submit" class="submit-overlay"></button>
                  <div class="slot-content">
                    <div class="slot-header">{{ slot.available ? 'Available' : 'Unavailable' }}</div>
                    <div class="slot-action-text">{{ slot.available ? 'Set to Unavailable' : 'Set to Available' }}</div>
                  </div>
                  <div class="slot-time">{{ slot.time_range }}</div>
                </form>
              </div>
            </template>
          </div>
        </div>
      </template>
    </div>

    <div class="divider-right"></div>

    <div class="panel" :class="{ open: selected_appointment || edit_profile }">
      <template v-if="edit_profile">
        <div class="panel-header">
          <h3>Edit Profile</h3>
          <a href="#" class="close-panel" title="Close" @click.prevent="closePanel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </a>
        </div>

        <form @submit.prevent="saveProfile">
          <div class="doctor-details-edit">
            <div class="profile-avatar-wrap">
              <label class="profile-avatar-picker">
                <span class="profile-avatar-circle" :class="{ filled: Boolean(profileForm.profile_image_data) }">
                  <img
                    v-if="profileForm.profile_image_data"
                    :src="profileForm.profile_image_data"
                    alt="Profile preview"
                    class="profile-avatar-image"
                  >
                  <span v-else class="profile-avatar-fallback">{{ getProfileInitials(profileForm.name) }}</span>
                </span>
                <input type="file" accept="image/*" class="profile-avatar-input" @change="handleProfileImageChange">
              </label>
              <div class="profile-avatar-actions">
                <span class="profile-avatar-hint">Tap the circle to upload a photo</span>
                <button
                  v-if="profileForm.profile_image_data"
                  type="button"
                  class="profile-avatar-remove"
                  @click="removeProfileImage"
                >
                  Remove Photo
                </button>
              </div>
            </div>
            <div class="detail-row">
              <span class="detail-label">Name</span>
              <input
                v-model.trim="profileForm.name"
                type="text"
                name="name"
                class="sidebar-input"
                minlength="2"
                maxlength="120"
                required
              >
            </div>
            <div class="detail-row">
              <span class="detail-label">Email</span>
              <input
                v-model.trim="profileForm.email"
                type="email"
                name="email"
                class="sidebar-input"
                maxlength="120"
                required
              >
            </div>
            <div class="detail-row">
              <span class="detail-label">New Password</span>
              <input
                v-model="profileForm.password"
                type="password"
                name="password"
                class="sidebar-input"
                placeholder="Unchanged"
                minlength="6"
                maxlength="120"
              >
            </div>
            <div class="detail-row">
              <span class="detail-label">Experience (Yrs)</span>
              <input
                v-model="profileForm.experience_years"
                type="number"
                name="experience_years"
                class="sidebar-input"
                min="0"
                max="80"
              >
            </div>
            <div class="detail-row">
              <span class="detail-label">Specialization</span>
              <input
                v-model.trim="profileForm.specialization"
                type="text"
                name="specialization"
                class="sidebar-input"
                minlength="2"
                maxlength="120"
              >
            </div>
            <div class="detail-row">
              <span class="detail-label">Department</span>
              <input
                v-model.trim="profileForm.dept"
                type="text"
                name="dept"
                class="sidebar-input"
                minlength="2"
                maxlength="120"
              >
            </div>

            <button type="submit" class="save-btn">Save Changes</button>
          </div>
        </form>
      </template>

      <template v-else-if="selected_appointment">
        <div class="panel-header">
          <h3>Appointment Details</h3>
          <a href="#" class="close-panel" title="Close" @click.prevent="closePanel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </a>
        </div>
        <div class="appointment-details">
          <div class="detail-item">
            <span class="detail-label">Patient</span>
            <span class="detail-value">{{ selected_appointment.patient_name }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Time</span>
            <span class="detail-value">{{ selected_appointment.formatted_time }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Date</span>
            <span class="detail-value">{{ selected_appointment.formatted_date }}</span>
          </div>
        </div>

        <form class="update-details-form" @submit.prevent="saveAppointment">
          <div class="form-group">
            <label for="diagnosis">Diagnosis</label>
            <textarea
              id="diagnosis"
              v-model="selected_appointment.diagnosis"
              rows="3"
              placeholder="Enter diagnosis..."
              minlength="2"
              maxlength="500"
              required
            ></textarea>
          </div>
          <div class="form-group">
            <label for="prescription">Prescription</label>
            <textarea
              id="prescription"
              v-model="selected_appointment.prescription"
              rows="5"
              placeholder="Enter prescription..."
              minlength="2"
              maxlength="500"
              required
            ></textarea>
          </div>
          <div class="form-group">
            <label for="doctor_notes">Doctor Notes</label>
            <textarea
              id="doctor_notes"
              v-model="selected_appointment.doctor_notes"
              rows="3"
              placeholder="Private notes..."
              maxlength="500"
            ></textarea>
          </div>
          <button type="submit" class="submit-button">Mark as Completed</button>
        </form>

        <form class="cancel-form" @submit.prevent="cancelAppointment">
          <button type="submit" class="cancel-button">Cancel Appointment</button>
        </form>
      </template>
    </div>
  </div>
</template>

<style scoped>
body {
  margin: 0;
  padding: 0;
  background: #f8f9fa;
  color: #000;
  font-family: sans-serif;
  min-height: 100vh;
  user-select: none;
  display: flex;
}
.container {
  display: flex;
  height: 100vh;
  width: 100%;
  margin: 0;
  background: white;
  position: relative;
}
.left {
  width: 20%;
  padding: 1.5rem;
  overflow-y: auto;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  z-index: 10;
  flex-shrink: 0;
}
.sidebar-header {
  font-size: 1.2rem;
  font-weight: 500;
  text-align: left;
  margin: 0 0 1rem 0;
  line-height: 1.2;
}
.sidebar-name {
  margin: 0 0 2rem 0;
  font-size: 1rem;
  color: #666;
  text-align: left;
}
.sidebar-calendar {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.calendar-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  transition: background-color 0.2s;
  text-decoration: none;
  color: inherit;
}
.calendar-item.selected {
  color: #007bff;
  font-weight: 500;
}
.calendar-item.selected .calendar-label,
.calendar-item.selected .calendar-count {
  color: #007bff;
  font-weight: 600;
}
.calendar-label {
  font-size: 1rem;
  color: #333;
}
.calendar-count {
  font-weight: 500;
  color: #333;
  text-align: right;
  min-width: 3rem;
}
.edit-profile-btn {
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  color: #333;
  margin-top: auto;
  margin-bottom: 1rem;
  transition: color 0.2s;
}
.edit-profile-btn:hover {
  color: #007bff;
}

.logout {
  color: #dc3545;
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  align-self: flex-start;
}
.divider {
  width: 1px;
  background: #e5e7eb;
  flex-shrink: 0;
}
.right {
  width: 80%;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  height: 100vh;
  overflow-y: auto;
  min-height: 600px;
  transition: width 0.3s ease;
  position: relative;
  z-index: 5;
  flex: 1;
}
.right.panel-open {
  width: 40%;
}
.divider-right {
  width: 1px;
  background: #e5e7eb;
  display: none;
  height: 100%;
  flex-shrink: 0;
}
.right.panel-open + .divider-right {
  display: block;
}
.day-slots-section {
  background: white;
  padding: 1.5rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.day-slots-section h3 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  font-weight: 500;
}
.slot-help-text {
  font-size: 0.9rem;
  color: #999;
  margin-top: -0.8rem;
  margin-bottom: 1.5rem;
  font-weight: 400;
}
.dashboard-job-note {
  padding: 1.5rem 1.5rem 0;
}
.job-notice {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.4;
  color: #7b8794;
}
.notice-inline {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}
.job-send-link {
  border: none;
  background: transparent;
  color: #005eff;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 500;
  padding: 0;
  cursor: pointer;
}
.job-send-link:hover {
  text-decoration: underline;
}
.slots-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 1.5rem;
}
.slot-card {
  background: #f1f1f1;
  border-radius: 2rem;
  padding: 1.5rem;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.2s;
  position: relative;
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: inherit;
}
.slot-content {
  position: absolute;
  top: 46%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}
.slot-time {
  position: absolute;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  font-size: 1rem;
  font-weight: 500;
}
.slot-header {
  font-size: 1.2rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
}
.slot-action-text {
  font-size: 0.9rem;
  color: #666;
}
.slot-booked {
  background: #f1f1f1;
}
.slot-available {
  background: #d4edda;
  color: #155724;
}
.slot-unavailable {
  background: #f8d7da;
  color: #721c24;
}
.availability-form,
.cancel-form-slot {
  position: relative;
  margin: 0;
  width: 100%;
  height: 100%;
}
.submit-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  z-index: 1;
  border: none;
  background: none;
}
.all-appointments-section {
  background: white;
  padding: 1.5rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.all-appointments-section h3 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  font-weight: 500;
}
.past-section {
  background: white;
  padding: 1.5rem;
  margin-bottom: 0;
}
.past-appointment-card {
  background: #f1f1f1;
  border-radius: 1rem;
  padding: 1rem;
}
.past-appointment-line {
  margin-bottom: 1rem;
}
.past-appointment-line:last-child {
  margin-bottom: 0;
}
.past-appointment-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
}
.history-edit-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.4rem;
}
.history-textfield {
  border: none;
  background: transparent;
  color: #666;
  font-size: 0.9rem;
  padding: 0;
  outline: none;
  font-family: inherit;
  width: 100%;
}
.history-textfield::placeholder {
  color: #999;
}
.available-doctors {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.doctor-avatar {
  width: 40px;
  height: 40px;
  background: #7c7c7c;
  border-radius: 50%;
  flex-shrink: 0;
}
.doctor-info {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
.doctor-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
}
.doctor-dept {
  margin: 0;
  color: #666;
  font-size: 0.9rem;
}
.doctor-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.action-button {
  background: #e7f1ff;
  color: #005eff;
  border: none;
  padding: 0 1.5rem;
  height: 40px;
  line-height: 40px;
  border-radius: 5rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.9rem;
  text-decoration: none;
  display: inline-block;
  text-align: center;
  transition: background-color 0.2s, color 0.2s;
}
.action-button:hover {
  background: #d0e4ff;
}

.panel {
  width: 0;
  padding: 0;
  overflow: hidden;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  transition: width 0.3s ease, padding 0.3s ease;
  z-index: 0;
  flex-shrink: 0;
  min-width: 0;
}
.panel.open {
  width: 30%;
  padding: 1.5rem;
  overflow-y: auto;
}
.panel:empty {
  display: none;
}
.panel-header {
  font-size: 1.2rem;
  font-weight: 500;
  margin: 0 0 1rem 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 500;
  text-align: left;
  line-height: 1.2;
}
.close-panel {
  background: #e9ecef;
  border: none;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  cursor: pointer;
  color: #666;
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s, color 0.2s;
}
.close-panel:hover {
  background: #dee2e6;
  color: #000;
}
.close-panel svg {
  width: 16px;
  height: 16px;
}
.appointment-details {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
}
.detail-item {
  display: flex;
  justify-content: space-between;
}
.detail-label {
  font-weight: 500;
  color: #666;
}
.detail-value {
  font-weight: 500;
}
.cancel-button {
  background-color: #f1f1f1;
  color: #dc3545;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 5rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.9rem;
  text-decoration: none;
  display: block;
  width: 100%;
  text-align: center;
  transition: background-color 0.2s;
  margin-top: 1rem;
}
.cancel-form {
  padding-bottom: 1rem;
}
.cancel-button:hover {
  background: #e2e6ea;
}

.no-appointment-card {
  background: #f1f1f1;
  border-radius: 1rem;
  padding: 1rem;
  margin-bottom: 1rem;
  text-align: center;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
  width: 100%;
}
.form-group label {
  font-weight: 500;
  color: #666;
  margin-bottom: 0.25rem;
  display: block;
}
textarea {
  padding: 0.8rem 1rem;
  border: 1.5px solid rgb(0 0 0 / 25%);
  background: white;
  border-radius: 1rem;
  font-size: 1rem;
  color: #000000;
  outline: none;
  transition: border-color 0.5s;
  font-weight: 400;
  box-sizing: border-box;
  width: 100%;
  resize: vertical;
}
textarea::placeholder {
  color: rgb(0 0 0 / 50%);
  font-size: 1rem;
}
.submit-button {
  width: 100%;
  background: #005eff;
  border: none;
  padding: 0.8rem 1rem;
  color: white;
  font-size: 0.85rem;
  font-weight: 500;
  border-radius: 10rem;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: 0.5rem;
}

.sidebar-input {
  background: transparent;
  border: none;
  font-family: inherit;
  font-size: 1rem;
  font-weight: 500;
  color: #000;
  text-align: right;
  width: 65%;
  outline: none;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}
.sidebar-input:hover,
.sidebar-input:focus {
  background: #f1f3f5;
}
.sidebar-input::placeholder {
  color: #bbb;
}

.profile-avatar-wrap {
  margin: 1.6rem auto 2.1rem;
  padding: 0 0.75rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.9rem;
}

.profile-avatar-picker {
  cursor: pointer;
}

.profile-avatar-circle {
  width: 132px;
  height: 132px;
  border-radius: 50%;
  background: #eef2f7;
  border: 1px solid #e1e7ef;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: #7a8797;
  font-size: 2rem;
  font-weight: 600;
}

.profile-avatar-circle.filled {
  background: #f5f7fb;
}

.profile-avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-avatar-fallback {
  line-height: 1;
}

.profile-avatar-input {
  display: none;
}

.profile-avatar-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  text-align: center;
}

.profile-avatar-hint {
  color: #7b8794;
  font-size: 0.82rem;
}

.profile-avatar-remove {
  border: none;
  background: transparent;
  color: #005eff;
  cursor: pointer;
  font-size: 0.82rem;
  padding: 0;
}

.doctor-details-edit .detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
  padding-bottom: 0.8rem;
}
.doctor-details-edit .detail-label {
  font-weight: 500;
  color: #666;
  flex-shrink: 0;
}

.save-btn {
  display: block;
  width: 100%;
  margin-top: 1rem;
  background: #e7f1ff;
  color: #007bff;
  border: none;
  padding: 0.8rem 1rem;
  border-radius: 6rem;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  transition: background-color 0.2s;
}
.save-btn:hover {
  background: #d0e4ff;
}

@media (max-width: 768px) {
  .container {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
  }
  .left {
    width: 100%;
  }
  .divider {
    width: 100%;
    height: 1px;
    background: #e5e7eb;
  }
  .right {
    width: 100%;
    height: auto;
    min-height: auto;
    justify-content: flex-start;
  }
  .right.panel-open {
    width: 100%;
  }
  .panel {
    width: 100%;
    transition: none;
    height: auto;
    position: static;
    right: auto;
    padding: 1.5rem;
    overflow-y: auto;
    min-width: 0;
  }
  .panel:not(.open) {
    width: 0;
    padding: 0;
    overflow: hidden;
  }
  .divider-right {
    display: none !important;
  }
  .slots-grid {
    grid-template-columns: 1fr;
    grid-template-rows: repeat(4, 1fr);
  }
  .calendar-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }
  .calendar-count {
    align-self: flex-end;
  }
  .available-doctors {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
  .doctor-actions {
    width: 100%;
    justify-content: flex-start;
  }
  .action-button {
    flex: 1;
  }
  .profile-avatar-circle {
    width: 112px;
    height: 112px;
  }
}
</style>
