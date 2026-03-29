<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  bookAppointment,
  cancelPatientAppointment,
  createTreatmentExport,
  getDepartments,
  getDoctorBookingSlots,
  getPatientAppointments,
  getPatientExports,
  getPatientProfile,
  sendPatientExportAlertNow,
  sendPatientReminderNow,
  searchDoctors,
  updatePatientProfile,
} from '../services/patientService'
import { useAuthStore } from '../stores/auth'
import {
  getAppointmentHistoryDateTime,
  isAppointmentHistorical,
  normalizeAppointment,
  normalizeDepartment,
  normalizeUser,
} from '../utils/dashboardData'

const router = useRouter()
const authStore = useAuthStore()

const state = reactive({
  currentUser: null,
  departments: [],
  doctors: [],
  appointments: [],
  exports: [],
})

const selected_dept = ref('')
const search = ref('')
const doctor = ref(null)
const selected_slot = ref('')
const edit_profile = ref(false)
const sendingReminderNow = ref(false)
const sendingExportNow = ref(false)

const profileForm = reactive({
  name: '',
  email: '',
  password: '',
  profile_image_data: '',
})

let searchDebounceId = null
let exportPollId = null
const seenExportStatuses = new Map()

const jinjaemail = computed(() => state.currentUser?.email || '')
const current_user = computed(() => state.currentUser)
const departments = computed(() => state.departments)
const exports = computed(() => state.exports)

const past_appointments = computed(() =>
  [...state.appointments]
    .filter((appointment) => isAppointmentHistorical(appointment))
    .sort(
      (left, right) =>
        new Date(getAppointmentHistoryDateTime(right)) - new Date(getAppointmentHistoryDateTime(left)),
    ),
)

const upcoming_appointments = computed(() =>
  state.appointments
    .filter(
      (appointment) =>
        new Date(appointment.appointment_datetime) >= new Date() && appointment.status === 'scheduled',
    )
    .sort((left, right) => new Date(left.appointment_datetime) - new Date(right.appointment_datetime))
    .map((appointment) => ({
      ...appointment,
      formatted_date: formatAppointmentDate(appointment.appointment_datetime),
    })),
)

const dailyReminderNotice = computed(() => {
  const now = new Date()
  const todayAppointment = upcoming_appointments.value.find((appointment) => {
    const appointmentDate = new Date(appointment.appointment_datetime)
    return appointmentDate.toDateString() === now.toDateString()
  })

  if (todayAppointment) {
    return `Email reminder applies today for your visit at ${new Date(
      todayAppointment.appointment_datetime,
    ).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    })}.`
  }

  if (upcoming_appointments.value.length) {
    return 'Daily reminder emails are sent at 08:00 AM on the day of each scheduled visit.'
  }

  return ''
})

const exportNotice = computed(() => {
  const activeExport = state.exports.find((item) => item.status === 'queued' || item.status === 'running')
  if (activeExport) {
    return 'CSV export is in progress. An email alert will be sent when the document is ready.'
  }

  return 'When you generate a CSV, an email alert is sent after the document is ready.'
})

const available_doctors = computed(() => state.doctors)
const slot_sections = computed(() => doctor.value?.slot_sections ?? {})
const ordered_slot_sections = computed(() => {
  const sections = Object.entries(slot_sections.value).map(([date_name, slots]) => ({
    date_name,
    slots,
  }))

  const priority = {
    Today: 0,
    Tomorrow: 1,
  }

  return sections.sort((left, right) => {
    const leftPriority = priority[left.date_name] ?? 2
    const rightPriority = priority[right.date_name] ?? 2

    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority
    }

    if (leftPriority < 2) return 0

    return new Date(left.slots[0]?.slot_str || 0) - new Date(right.slots[0]?.slot_str || 0)
  })
})

const confirmSlotLabel = computed(() => {
  if (!selected_slot.value) {
    return 'Select a slot to continue'
  }

  return `Confirm Slot for ${formatAppointmentDate(selected_slot.value)}`
})

function syncProfileForm() {
  profileForm.name = state.currentUser?.name || ''
  profileForm.email = state.currentUser?.email || ''
  profileForm.password = ''
  profileForm.profile_image_data = state.currentUser?.profile_image_data || ''
}

async function loadPatientProfile() {
  const response = await getPatientProfile()
  state.currentUser = normalizeUser(response.data.patient)
  syncProfileForm()
}

async function loadAppointments() {
  const response = await getPatientAppointments()
  state.appointments = response.data.appointments.map(normalizeAppointment)
}

async function loadExports() {
  const response = await getPatientExports()
  state.exports = response.data.exports

  for (const exportJob of state.exports) {
    const previousStatus = seenExportStatuses.get(exportJob.id)
    if (previousStatus && previousStatus !== exportJob.status) {
      if (exportJob.status === 'completed') {
        window.alert('Your treatment export is ready for download.')
      } else if (exportJob.status === 'failed') {
        window.alert(exportJob.error_message || 'A treatment export failed.')
      }
    }
    seenExportStatuses.set(exportJob.id, exportJob.status)
  }
}

async function loadDepartments() {
  const response = await getDepartments()
  state.departments = response.data.departments.map(normalizeDepartment)

  if (!selected_dept.value && state.departments.length) {
    selected_dept.value = state.departments[0].name
  }
}

async function loadDoctors() {
  if (!selected_dept.value) {
    state.doctors = []
    return
  }

  const response = await searchDoctors({
    search: search.value.trim(),
    department: selected_dept.value,
  })
  state.doctors = response.data.doctors.map(normalizeUser)
}

function formatAppointmentDate(dateTime) {
  const appointmentDate = new Date(dateTime)
  const today = new Date()
  const delta = Math.floor(
    (appointmentDate.setHours(0, 0, 0, 0) - new Date(today).setHours(0, 0, 0, 0)) / 86400000,
  )

  let dayLabel
  if (delta === 0) {
    dayLabel = 'Today'
  } else if (delta === 1) {
    dayLabel = 'Tomorrow'
  } else {
    dayLabel = new Date(dateTime).toLocaleDateString('en-US', {
      month: 'long',
      day: '2-digit',
      year: 'numeric',
    })
  }

  const timeLabel = new Date(dateTime).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })

  return `${dayLabel} at ${timeLabel}`
}

function formatPastAppointment(appointment) {
  const date = new Date(getAppointmentHistoryDateTime(appointment))
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

async function selectDepartment(name) {
  selected_dept.value = name
  doctor.value = null
  selected_slot.value = ''
  edit_profile.value = false

  try {
    await loadDoctors()
  } catch (error) {
    window.alert(error.message || 'Unable to load doctors for this department.')
  }
}

async function openDoctorPanel(item) {
  try {
    const response = await getDoctorBookingSlots(item.uid)
    doctor.value = {
      ...normalizeUser(response.data.doctor),
      slot_sections: response.data.slot_sections || {},
    }
    selected_slot.value = ''
    edit_profile.value = false
  } catch (error) {
    window.alert(error.message || 'Unable to load doctor details.')
  }
}

function openEditProfile() {
  edit_profile.value = true
  doctor.value = null
}

function closePanel() {
  edit_profile.value = false
  doctor.value = null
  selected_slot.value = ''
}

function chooseSlot(slot) {
  if (slot.disabled) return
  selected_slot.value = slot.slot_str
  
  setTimeout(() => {
    const panel = document.querySelector('.doctor-panel')
    if (panel) {
      panel.scrollTo({ top: panel.scrollHeight, behavior: 'smooth' })
    }
  }, 400)
}

function getProfileInitials(name) {
  return (name || 'User')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || 'U'
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
    const response = await updatePatientProfile({
      name: profileForm.name,
      email: profileForm.email,
      password: profileForm.password,
      profile_image_data: profileForm.profile_image_data,
    })

    state.currentUser = normalizeUser(response.data.patient)
    syncProfileForm()
    await authStore.refreshUser()
    window.alert('Profile updated successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to update profile.')
  }
}

async function cancelAppointment(appointment) {
  try {
    await cancelPatientAppointment(appointment.aid)
    await loadAppointments()
    if (doctor.value) {
      await openDoctorPanel(doctor.value)
    }
    window.alert('Appointment cancelled successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to cancel appointment.')
  }
}

async function confirmAppointment() {
  if (!doctor.value || !selected_slot.value) {
    window.alert('Please select an appointment slot first.')
    return
  }

  try {
    await bookAppointment({
      doctor_id: doctor.value.uid,
      appointment_datetime: selected_slot.value,
    })
    await loadAppointments()
    await openDoctorPanel(doctor.value)
    selected_slot.value = ''
    window.alert('Appointment booked successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to book appointment.')
  }
}

function exportDownloadUrl(exportJobId) {
  return `/api/patient/exports/${exportJobId}/download`
}

function displayExportName(item) {
  if (!item.file_name) {
    return `treatment_history_${item.id}.csv`
  }

  const match = item.file_name.match(/(\d{8}_\d{6})/)
  if (match) {
    return `treatment_history_${match[1]}.csv`
  }

  return item.file_name
}

async function triggerTreatmentExport() {
  try {
    await createTreatmentExport()
    await loadExports()
    window.alert('Treatment export started successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to start treatment export.')
  }
}

async function triggerReminderSendNow() {
  if (sendingReminderNow.value) return

  sendingReminderNow.value = true
  try {
    const response = await sendPatientReminderNow()
    window.alert(response.message || 'Reminder email sent successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to send the reminder right now.')
  } finally {
    sendingReminderNow.value = false
  }
}

async function triggerExportAlertSendNow() {
  if (sendingExportNow.value) return

  sendingExportNow.value = true
  try {
    const response = await sendPatientExportAlertNow()
    window.alert(response.message || 'Treatment document email sent successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to send the treatment document email right now.')
  } finally {
    sendingExportNow.value = false
  }
}

async function handleLogout() {
  await authStore.logout()
  await router.push({ name: 'signin' })
}

onMounted(async () => {
  try {
    await authStore.initialize()
    await loadPatientProfile()
    await loadAppointments()
    await loadExports()
    await loadDepartments()
    await loadDoctors()
  } catch (error) {
    window.alert(error.message || 'Unable to load the patient dashboard.')
  }

  exportPollId = window.setInterval(() => {
    loadExports().catch(() => {})
  }, 5000)
})

watch(search, () => {
  window.clearTimeout(searchDebounceId)
  searchDebounceId = window.setTimeout(async () => {
    try {
      await loadDoctors()
    } catch (error) {
      window.alert(error.message || 'Unable to refresh doctor search.')
    }
  }, 250)
})

onUnmounted(() => {
  if (exportPollId) {
    window.clearInterval(exportPollId)
  }
})
</script>

<template>
  <div class="container">
    <div class="left">
      <div>
        <div class="sidebar-header">Local Hospital Management System</div>
        <div class="sidebar-name">Welcome, {{ jinjaemail }}</div>
      </div>

      <RouterLink to="/patient/payments" class="sidebar-nav-link">Payments</RouterLink>
      <a href="#" class="edit-profile-btn" @click.prevent="openEditProfile">Edit Profile</a>

      <a href="#" class="logout" @click.prevent="handleLogout">Logout</a>
    </div>
    <div class="divider"></div>
    <div class="right" :class="{ 'panel-open': doctor || edit_profile }" id="main-content">
      <template v-if="past_appointments.length">
        <div class="past-section">
          <div class="past-appointment-card">
            <div v-for="appt in past_appointments" :key="appt.aid" class="past-appointment-line">
              <div class="past-appointment-info">
                <h4>Past appointment with {{ appt.doctor.name }} on {{ formatPastAppointment(appt) }}</h4>
                <p class="past-diagnosis">Diagnosis: {{ appt.diagnosis || 'N/A' }}</p>
                <p class="past-prescription">Prescription: {{ appt.prescription || 'N/A' }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div class="upcoming-section">
        <h3>Upcoming Appointments</h3>
        <p v-if="dailyReminderNotice" class="job-notice notice-inline">
          <span>{{ dailyReminderNotice }}</span>
          <button type="button" class="job-send-link" @click="triggerReminderSendNow">
            {{ sendingReminderNow ? 'Sending...' : 'Send Now' }}
          </button>
        </p>
        <template v-if="upcoming_appointments.length">
          <div v-for="appt in upcoming_appointments" :key="appt.aid" class="available-doctors">
            <div class="doctor-avatar"></div>
            <div class="doctor-info">
              <h4>{{ appt.doctor.name }}</h4>
              <p class="doctor-dept">{{ appt.formatted_date }}</p>
            </div>
            <div class="doctor-actions">
              <form style="margin: 0; display: inline;" @submit.prevent="cancelAppointment(appt)">
                <button type="submit" class="action-button">Cancel</button>
              </form>
            </div>
          </div>
        </template>
        <div v-else class="no-appointment-card">
          <p style="margin: 0; color: #686868;">No upcoming appointments.</p>
        </div>
      </div>
      <div class="book-section">
        <h3>Book an Appointment</h3>

        <div class="department-buttons">
          <template v-if="departments.length">
            <a
              v-for="d in departments"
              :key="d.did"
              href="#"
              class="dept-button"
              :class="{ selected: selected_dept === d.name }"
              @click.prevent="selectDepartment(d.name)"
            >
              {{ d.name }}
            </a>
          </template>
          <p v-else style="color: #666; font-style: italic;">No departments available.</p>
        </div>

        <div class="controls-row">
          <div class="search-wrapper">
            <form method="get" style="width: 100%; margin: 0;" @submit.prevent>
              <input
                v-model="search"
                type="text"
                name="search"
                class="pill-input"
                placeholder="Search doctors in this department..."
              >
              <button type="submit" class="search-btn-icon">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="11" cy="11" r="8"></circle>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
              </button>
            </form>
          </div>
        </div>

        <template v-if="selected_dept">
          <div class="doctor-section">
            <template v-if="available_doctors.length">
              <div v-for="doc in available_doctors" :key="doc.uid" class="available-doctors">
                <div class="doctor-avatar"></div>
                <div class="doctor-info">
                  <h4>{{ doc.name }}</h4>
                  <p class="doctor-dept">{{ doc.email }}</p>
                </div>
                <div class="doctor-actions">
                  <a href="#" class="action-button" @click.prevent="openDoctorPanel(doc)">About</a>
                  <a href="#" class="action-button request" @click.prevent="openDoctorPanel(doc)">Appointment Slots</a>
                </div>
              </div>
            </template>
            <p v-else class="no-doctors">No doctors available in {{ selected_dept }}.</p>
          </div>
        </template>
      </div>
      <div class="export-section">
        <div class="export-header-row">
          <h3>Treatment History Documents</h3>
          <button type="button" class="export-button" @click="triggerTreatmentExport">Export as CSV</button>
        </div>
        <p class="job-notice notice-inline">
          <span>{{ exportNotice }}</span>
          <button type="button" class="job-send-link" @click="triggerExportAlertSendNow">
            {{ sendingExportNow ? 'Sending...' : 'Send Now' }}
          </button>
        </p>
        <template v-if="exports.length">
          <div v-for="item in exports" :key="item.id" class="available-doctors export-row">
            <div class="doctor-avatar"></div>
            <div class="doctor-info export-info">
              <h4 :title="item.file_name || `Treatment Export #${item.id}`">{{ displayExportName(item) }}</h4>
              <p class="doctor-dept" style="text-transform: capitalize;">{{ item.status }}{{ item.completed_at ? ` • ${item.completed_at.slice(0, 16).replace('T', ' ')}` : '' }}</p>
            </div>
            <div class="doctor-actions export-actions">
              <a
                v-if="item.status === 'completed'"
                :href="exportDownloadUrl(item.id)"
                class="action-button request"
              >Download</a>
              <span v-else class="action-button export-status">{{ item.status }}</span>
            </div>
          </div>
        </template>
        <div v-else class="no-appointment-card">
          <p style="margin: 0; color: #686868;">No exports generated yet.</p>
        </div>
      </div>
    </div>
    <div class="divider-right"></div>
    <div class="doctor-panel" :class="{ open: doctor || edit_profile }">
      <template v-if="edit_profile">
        <div class="doctor-panel-header">
          <h3>Edit Profile</h3>
          <a href="#" class="close-panel" title="Close" @click.prevent="closePanel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </a>
        </div>

        <form @submit.prevent="saveProfile">
          <div class="patient-details-edit">
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

            <button type="submit" class="save-btn">Save Changes</button>
          </div>
        </form>
      </template>

      <template v-else-if="doctor">
        <div class="doctor-panel-header">
          <h3>{{ doctor.name }}</h3>
          <a href="#" class="close-panel" @click.prevent="closePanel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </a>
        </div>
        <div class="doctor-details">
          <div class="detail-item">
            <span class="detail-label">Experience:</span>
            <span class="detail-value">{{ doctor.experience_years }} years</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Specialization:</span>
            <span class="detail-value">{{ doctor.specialization || 'N/A' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Department:</span>
            <span class="detail-value">{{ doctor.department ? doctor.department.name : 'N/A' }}</span>
          </div>
        </div>
        <div class="appointment-slots-section">
          <h4>Appointment Slots</h4>
          <div v-for="section in ordered_slot_sections" :key="section.date_name" class="date-section">
            <h5>{{ section.date_name }}</h5>
            <div class="slots-row">
              <a
                v-for="slot in section.slots"
                :key="slot.slot_str"
                href="#"
                class="slot-button"
                :class="{ selected: selected_slot === slot.slot_str }"
                :style="slot.disabled ? 'pointer-events: none; opacity: 0.6;' : ''"
                @click.prevent="chooseSlot(slot)"
              >
                <span class="start-time">{{ slot.start }}</span> - <span class="end-time">{{ slot.end }}</span>
              </a>
            </div>
          </div>
        </div>
        <div class="confirm-section">
          <h4>Confirm Selected Slot</h4>
          <form style="width: 100%;" @submit.prevent="confirmAppointment">
            <button type="submit" class="confirm-button" :disabled="!selected_slot">
              {{ confirmSlotLabel }}
            </button>
          </form>
        </div>
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
  width: 22%;
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
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #666;
  text-align: left;
}
.logout {
  color: #dc3545;
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  align-self: flex-start;
}
.sidebar-nav-link {
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  color: #333;
  align-self: flex-start;
  margin-bottom: 1rem;
  transition: color 0.2s;
}
.sidebar-nav-link:first-of-type {
  margin-top: auto;
}
.sidebar-nav-link:hover {
  color: #007bff;
}
.edit-profile-btn {
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  color: #333;
  margin-bottom: 1rem;
  transition: color 0.2s;
}
.edit-profile-btn:hover {
  color: #007bff;
}

.divider {
  width: 1px;
  background: #e5e7eb;
  flex-shrink: 0;
}
.right {
  width: 78%;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 600px;
  transition: width 0.3s ease;
  position: relative;
  z-index: 5;
  flex: 1;
}
.right.panel-open {
  width: 37%;
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
.past-diagnosis,
.past-prescription {
  margin: 0 0 0.25rem 0;
  color: #666;
  font-size: 0.9rem;
}
.upcoming-section {
  background: white;
  padding: 1.5rem;
  margin-bottom: 2rem;
}
.upcoming-section h3 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  font-weight: 500;
}
.job-notice {
  margin: -0.35rem 0 1rem 0;
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
.export-section {
  background: white;
  padding: 1.5rem;
  margin-bottom: 2rem;
}
.export-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.export-header-row h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 500;
}
.export-button {
  background: #e7f1ff;
  color: #005eff;
  border: none;
  padding: 0 1.2rem;
  height: 36px;
  border-radius: 5rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.85rem;
  transition: background-color 0.2s, color 0.2s;
  flex-shrink: 0;
}
.export-button:hover {
  background: #d0e4ff;
}
.no-appointment-card {
  background: #f1f1f1;
  border-radius: 1rem;
  padding: 1rem;
  margin-bottom: 1rem;
  text-align: center;
}
.book-section {
  background: white;
  padding: 1.5rem;
  margin-bottom: 2rem;
}
.book-section h3 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  font-weight: 500;
}
.no-doctors {
  color: #666;
  font-style: italic;
  margin-top: 1rem;
}

.department-buttons {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}
.dept-button {
  background: #e9ecef;
  padding: 0.8rem 1.5rem;
  border-radius: 1rem;
  cursor: pointer;
  font-weight: 500;
  text-decoration: none;
  color: inherit;
  display: inline-block;
  text-align: center;
  transition: background-color 0.2s, color 0.2s;
}
.dept-button:hover {
  background: #dee2e6;
}
.dept-button.selected {
  background: #535353;
  color: white;
  border-color: #535353;
}

.controls-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}
.search-wrapper {
  flex: 1;
  position: relative;
}
.pill-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.8rem 3.5rem 0.8rem 1.5rem;
  border: 1.5px solid #dadada;
  border-radius: 5rem;
  font-size: 0.95rem;
  outline: none;
  background: white;
  font-family: inherit;
  height: 50px;
}
.pill-input::placeholder {
  color: #8a8a8a;
  opacity: 1;
  font-weight: 400;
}
.search-btn-icon {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  background: #e9ecef;
  border: none;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
}

.doctor-section {
  margin-bottom: 2rem;
}
.available-doctors {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
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
  gap: 1rem;
  align-items: center;
  flex-wrap: wrap;
}
.export-row {
  align-items: center;
}
.export-info {
  min-width: 0;
  overflow: hidden;
}
.export-info h4 {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.export-actions {
  flex-shrink: 0;
}
.action-button {
  background: #e9ecef;
  border: none;
  padding: 0 1.5rem;
  height: 40px;
  line-height: 40px;
  border-radius: 5rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.9rem;
  text-decoration: none;
  color: inherit;
  display: inline-block;
  text-align: center;
  transition: background-color 0.2s, color 0.2s;
}
.action-button:hover {
  background: #dee2e6;
}
.action-button.request {
  background-color: #007bff;
  color: white;
}
.action-button.export-status {
  cursor: default;
  text-transform: capitalize;
}

@media (max-width: 1200px) {
  .export-row {
    align-items: flex-start;
  }

  .export-actions {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
}
.doctor-panel {
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
.doctor-panel.open {
  width: 33%;
  padding: 1.5rem 1.75rem;
  overflow-y: auto;
  overflow-x: hidden;
}
.doctor-panel:empty {
  display: none;
}
.doctor-panel-header {
  font-size: 1.2rem;
  font-weight: 500;
  margin: 0 0 1.5rem 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.doctor-panel h3 {
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
.doctor-details {
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
.appointment-slots-section {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.appointment-slots-section h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 500;
}
.date-section {
  margin-bottom: 1.5rem;
}
.date-section h5 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 500;
  color: #666;
}
.slots-row {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
}
.slot-form {
  display: inline-block;
  flex: 1;
}
.slot-button {
  background: #e9ecef;
  border: none;
  padding: 0.8rem;
  border-radius: 5rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.85rem;
  color: inherit;
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 0;
  width: 100%;
  min-height: 46px;
  transition: background-color 0.2s, color 0.2s;
  text-align: center;
  gap: 0.2rem;
  text-decoration: none;
  white-space: nowrap;
}
.slot-button:hover:not(:disabled) {
  background: #dee2e6;
}
.slot-button.selected:hover {
  background: #007bff;
  color: white;
}
.slot-button:disabled {
  background: #e9ecef;
  color: #999;
  cursor: not-allowed;
  opacity: 0.6;
}
.slot-button.selected {
  background: #007bff;
  color: white;
}
.slot-button .start-time,
.slot-button .end-time {
  font-size: 0.85rem;
}
.confirm-section {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.confirm-section h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 500;
  color: #666;
}
.confirm-button {
  background-color: #007bff;
  color: white;
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
  transition: background-color 0.2s, color 0.2s;
}
.confirm-button:hover:not(:disabled) {
  background-color: #0056b3;
}
.confirm-button:disabled {
  background-color: #ccc;
  color: #666;
  cursor: not-allowed;
  opacity: 0.6;
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

.patient-details-edit .detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
  padding-bottom: 0.8rem;
}
.patient-details-edit .detail-label {
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
  .doctor-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 100%;
    height: 100vh;
    z-index: 9999;
    background: white;
    box-shadow: -5px 0 15px rgba(0, 0, 0, 0.1);
    transform: translateX(100%);
    transition: transform 0.3s ease;
    box-sizing: border-box;
    overflow-y: auto;
  }
  .doctor-panel.open {
    width: 100%;
    transform: translateX(0);
    padding: 1.5rem;
  }
  .doctor-panel:not(.open) {
    width: 100%;
    padding: 1.5rem;
    overflow: auto;
  }
  .divider-right {
    display: none !important;
  }
  .department-buttons {
    flex-direction: column;
  }
  .available-doctors {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  .doctor-actions {
    width: 100%;
    justify-content: flex-start;
  }
  .action-button {
    flex: 1;
  }
  .slots-row {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .slot-button {
    min-width: 80px;
  }
  .profile-avatar-circle {
    width: 112px;
    height: 112px;
  }
}
</style>
