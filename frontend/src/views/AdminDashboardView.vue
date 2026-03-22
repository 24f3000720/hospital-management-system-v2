<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  getAdminAnalytics,
  getAdminAppointmentDetail,
  getAdminAppointments,
  getAdminDoctors,
  getAdminPatients,
  getAdminStats,
  getAdminUserDetail,
  updateAdminAppointment,
  updateAdminUser,
  updateAdminUserBlacklist,
} from '../services/adminService'
import { useAuthStore } from '../stores/auth'
import {
  getAppointmentHistoryDateTime,
  isAppointmentHistorical,
  normalizeAppointment,
  normalizeUser,
} from '../utils/dashboardData'

const router = useRouter()
const authStore = useAuthStore()

const state = reactive({
  userEmail: '',
  doctors: [],
  patients: [],
  appointments: [],
  stats: {
    total_doctors: 0,
    total_patients: 0,
    total_appointments: 0,
    scheduled_appointments: 0,
    completed_appointments: 0,
    cancelled_appointments: 0,
  },
  analytics: {
    appointment_trend: { labels: [], values: [] },
    specialization_demand: { labels: [], values: [] },
  },
})

const tab = ref('doctors')
const search = ref('')
const appt_tab = ref('upcoming')
const selected_user = ref(null)
const selected_appointment = ref(null)
const user_appointments = ref([])
const selectedUserPassword = ref('')

let searchDebounceId = null
const trendCanvas = ref(null)
const specializationCanvas = ref(null)
let trendChart = null
let specializationChart = null

const jinjaemail = computed(() => state.userEmail)
const total_doctors = computed(() => state.stats.total_doctors)
const total_patients = computed(() => state.stats.total_patients)
const total_appointments = computed(() => state.stats.total_appointments)
const scheduled_appointments = computed(() => state.stats.scheduled_appointments || 0)
const completed_appointments = computed(() => state.stats.completed_appointments || 0)
const cancelled_appointments = computed(() => state.stats.cancelled_appointments || 0)
const today_appointment_count = computed(() => state.analytics.appointment_trend.values?.[0] || 0)
const doctors = computed(() => state.doctors)
const patients = computed(() => state.patients)
const appointments = computed(() => state.appointments)
const completion_rate = computed(() => {
  if (!total_appointments.value) return 0
  return Math.round((completed_appointments.value / total_appointments.value) * 100)
})
const adminJobNotice = computed(() => {
  const now = new Date()
  const notices = []

  if (today_appointment_count.value > 0) {
    notices.push(`${today_appointment_count.value} patient reminder email(s) are due today at 08:00 AM`)
  }

  if (now.getDate() === 1) {
    notices.push('monthly doctor PDF/email reports are due today at 08:30 AM')
  }

  if (!notices.length) {
    return 'No scheduled email jobs are due today.'
  }

  return `Automated jobs today: ${notices.join(' and ')}.`
})
const filtered_user_history = computed(() =>
  [...user_appointments.value]
    .filter((appointment) => isAppointmentHistorical(appointment))
    .sort(
      (left, right) =>
        new Date(getAppointmentHistoryDateTime(right)) - new Date(getAppointmentHistoryDateTime(left)),
    ),
)

function replaceUserInCollections(updatedUser) {
  state.doctors = state.doctors.map((doctor) => (doctor.uid === updatedUser.uid ? updatedUser : doctor))
  state.patients = state.patients.map((patient) => (patient.uid === updatedUser.uid ? updatedUser : patient))

  state.appointments = state.appointments.map((appointment) => ({
    ...appointment,
    doctor: appointment.doctor?.uid === updatedUser.uid ? updatedUser : appointment.doctor,
    patient: appointment.patient?.uid === updatedUser.uid ? updatedUser : appointment.patient,
  }))

  user_appointments.value = user_appointments.value.map((appointment) => ({
    ...appointment,
    doctor: appointment.doctor?.uid === updatedUser.uid ? updatedUser : appointment.doctor,
    patient: appointment.patient?.uid === updatedUser.uid ? updatedUser : appointment.patient,
  }))

  if (selected_user.value?.uid === updatedUser.uid) {
    selected_user.value = updatedUser
  }
}

function replaceAppointmentInCollections(updatedAppointment) {
  state.appointments = state.appointments.map((appointment) =>
    appointment.aid === updatedAppointment.aid ? updatedAppointment : appointment,
  )

  user_appointments.value = user_appointments.value.map((appointment) =>
    appointment.aid === updatedAppointment.aid ? updatedAppointment : appointment,
  )

  if (selected_appointment.value?.aid === updatedAppointment.aid) {
    selected_appointment.value = updatedAppointment
  }
}

async function loadStats() {
  const response = await getAdminStats()
  state.stats = response.data
}

async function renderAnalyticsCharts() {
  await nextTick()

  if (!trendCanvas.value || !specializationCanvas.value) return

  const { default: Chart } = await import('chart.js/auto')

  if (trendChart) trendChart.destroy()
  if (specializationChart) specializationChart.destroy()

  trendChart = new Chart(trendCanvas.value, {
    type: 'bar',
    data: {
      labels: state.analytics.appointment_trend.labels,
      datasets: [
        {
          data: state.analytics.appointment_trend.values,
          backgroundColor: '#dfe7f2',
          borderRadius: 10,
          borderSkipped: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#5f6c7b', font: { size: 10 } } },
        y: { beginAtZero: true, ticks: { precision: 0, color: '#5f6c7b', font: { size: 10 } } },
      },
    },
  })

  specializationChart = new Chart(specializationCanvas.value, {
    type: 'doughnut',
    data: {
      labels: state.analytics.specialization_demand.labels,
      datasets: [
        {
          data: state.analytics.specialization_demand.values,
          backgroundColor: ['#535353', '#8f9baa', '#c8d2df', '#dfe7f2', '#edf2f7'],
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      cutout: '62%',
    },
  })
}

async function loadAnalytics() {
  const response = await getAdminAnalytics()
  state.analytics = response.data
  await renderAnalyticsCharts()
}

async function loadTabData() {
  if (tab.value === 'doctors') {
    const response = await getAdminDoctors(search.value.trim())
    state.doctors = response.data.doctors.map(normalizeUser)
    return
  }

  if (tab.value === 'patients') {
    const response = await getAdminPatients(search.value.trim())
    state.patients = response.data.patients.map(normalizeUser)
    return
  }

  const response = await getAdminAppointments({
    search: search.value.trim(),
    apptTab: appt_tab.value,
  })
  state.appointments = response.data.appointments.map(normalizeAppointment)
}

async function setTab(nextTab) {
  tab.value = nextTab
  selected_user.value = null
  selected_appointment.value = null
  user_appointments.value = []

  try {
    await loadTabData()
  } catch (error) {
    window.alert(error.message || 'Unable to load this section.')
  }
}

async function openUser(user) {
  try {
    const response = await getAdminUserDetail(user.uid)
    selected_user.value = normalizeUser(response.data.user)
    user_appointments.value = response.data.appointments.map(normalizeAppointment)
    selectedUserPassword.value = ''
    selected_appointment.value = null
  } catch (error) {
    window.alert(error.message || 'Unable to load user details.')
  }
}

async function openAppointment(appointment) {
  try {
    const response = await getAdminAppointmentDetail(appointment.aid)
    selected_appointment.value = normalizeAppointment(response.data.appointment)
    selected_user.value = null
    user_appointments.value = []
  } catch (error) {
    window.alert(error.message || 'Unable to load appointment details.')
  }
}

function closePanel() {
  selected_user.value = null
  selected_appointment.value = null
  user_appointments.value = []
  selectedUserPassword.value = ''
}

async function toggleBlacklist(user) {
  try {
    const response = await updateAdminUserBlacklist(user.uid, !user.blacklisted)
    replaceUserInCollections(normalizeUser(response.data.user))
    await Promise.all([loadStats(), loadAnalytics()])
  } catch (error) {
    window.alert(error.message || 'Unable to update blacklist status.')
  }
}

async function saveSelectedUser() {
  if (!selected_user.value) return
  if (!selected_user.value.name?.trim() || !selected_user.value.email?.trim()) {
    window.alert('Name and email are required.')
    return
  }
  if (selectedUserPassword.value && selectedUserPassword.value.length < 6) {
    window.alert('New password must be at least 6 characters long.')
    return
  }

  try {
    const payload = {
      name: selected_user.value.name,
      email: selected_user.value.email,
      password: selectedUserPassword.value,
    }

    if (selected_user.value.f_rid === 3) {
      payload.specialization = selected_user.value.specialization
      payload.experience_years = Number(selected_user.value.experience_years || 0)
      payload.department = selected_user.value.department?.name || ''
    }

    const response = await updateAdminUser(selected_user.value.uid, payload)
    replaceUserInCollections(normalizeUser(response.data.user))
    selectedUserPassword.value = ''
    await Promise.all([loadStats(), loadAnalytics()])
    window.alert('User details updated successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to update user details.')
  }
}

async function saveSelectedAppointment() {
  if (!selected_appointment.value) return
  if (!selected_appointment.value.diagnosis?.trim() || !selected_appointment.value.prescription?.trim()) {
    window.alert('Diagnosis and prescription are required before completing an appointment.')
    return
  }

  try {
    const response = await updateAdminAppointment(selected_appointment.value.aid, {
      status: 'completed',
      diagnosis: selected_appointment.value.diagnosis || '',
      prescription: selected_appointment.value.prescription || '',
      doctor_notes: selected_appointment.value.doctor_notes || '',
    })

    replaceAppointmentInCollections(normalizeAppointment(response.data.appointment))
    await Promise.all([loadStats(), loadAnalytics()])
    window.alert('Appointment updated successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to update appointment.')
  }
}

async function cancelSelectedAppointment() {
  if (!selected_appointment.value) return

  try {
    const response = await updateAdminAppointment(selected_appointment.value.aid, {
      status: 'cancelled',
      diagnosis: selected_appointment.value.diagnosis || '',
      prescription: selected_appointment.value.prescription || '',
      doctor_notes: selected_appointment.value.doctor_notes || '',
    })

    replaceAppointmentInCollections(normalizeAppointment(response.data.appointment))
    await Promise.all([loadStats(), loadAnalytics()])
    window.alert('Appointment cancelled successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to cancel appointment.')
  }
}

function formatDateTime(dateTime) {
  return new Date(dateTime).toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).replace(',', ' •')
}

function formatDate(dateTime) {
  return new Date(dateTime).toLocaleDateString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
  })
}

function formatTime(dateTime) {
  return new Date(dateTime).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

function formatHistoryDateTime(appointment) {
  return formatDateTime(getAppointmentHistoryDateTime(appointment))
}

function isFutureAppointment(appointment) {
  return new Date(appointment.appointment_datetime) > new Date()
}

async function handleLogout() {
  await authStore.logout()
  await router.push({ name: 'signin' })
}

onMounted(async () => {
  try {
    await authStore.initialize()
    state.userEmail = authStore.user?.email || ''
    await Promise.all([loadStats(), loadAnalytics()])
    await loadTabData()
  } catch (error) {
    window.alert(error.message || 'Unable to load the admin dashboard.')
  }
})

watch(search, () => {
  window.clearTimeout(searchDebounceId)
  searchDebounceId = window.setTimeout(async () => {
    try {
      await loadTabData()
    } catch (error) {
      window.alert(error.message || 'Unable to refresh this section.')
    }
  }, 250)
})

watch(appt_tab, async () => {
  if (tab.value !== 'appointments') return

  try {
    await loadTabData()
  } catch (error) {
    window.alert(error.message || 'Unable to refresh appointments.')
  }
})

onUnmounted(() => {
  if (trendChart) trendChart.destroy()
  if (specializationChart) specializationChart.destroy()
})
</script>

<template>
  <div class="container">
    <div class="left">
      <div>
        <div class="sidebar-header">Local Hospital Management System</div>
        <div class="sidebar-name">Welcome, {{ jinjaemail }}</div>
      </div>
      <a href="#" class="logout" @click.prevent="handleLogout">Logout</a>
    </div>

    <div class="divider"></div>
    <div class="right" :class="{ 'panel-open': selected_user || selected_appointment }">
      <div class="section-container">
        <div class="stats-grid">
          <a href="#" class="stat-card" :class="{ active: tab === 'doctors' }" @click.prevent="setTab('doctors')">
            <h4>Total Doctors</h4>
            <p class="stat-number">{{ total_doctors }}</p>
          </a>
          <a href="#" class="stat-card" :class="{ active: tab === 'patients' }" @click.prevent="setTab('patients')">
            <h4>Total Patients</h4>
            <p class="stat-number">{{ total_patients }}</p>
          </a>
          <a
            href="#"
            class="stat-card"
            :class="{ active: tab === 'appointments' }"
            @click.prevent="setTab('appointments')"
          >
            <h4>Total Appointments</h4>
            <p class="stat-number">{{ total_appointments }}</p>
          </a>
        </div>

        <div class="analytics-row">
          <div class="analytics-card">
            <div class="analytics-header">
              <h4>7 Day Appointment Trend</h4>
            </div>
            <div class="analytics-canvas-wrap">
              <canvas ref="trendCanvas"></canvas>
            </div>
          </div>
          <div class="analytics-card analytics-demand">
            <div class="analytics-header">
              <h4>Specialization Demand</h4>
            </div>
            <div class="analytics-canvas-wrap">
              <canvas ref="specializationCanvas"></canvas>
            </div>
          </div>
          <div class="analytics-card analytics-summary">
            <div class="analytics-header">
              <h4>Completion Rate</h4>
            </div>
            <div class="analytics-summary-body">
              <div class="analytics-summary-number">{{ completion_rate }}%</div>
              <div class="analytics-summary-meta">Completed appointments</div>
              <div class="analytics-summary-list">
                <span>Scheduled {{ scheduled_appointments }}</span>
                <span>Completed {{ completed_appointments }}</span>
                <span>Cancelled {{ cancelled_appointments }}</span>
              </div>
            </div>
          </div>
        </div>
        <p class="job-notice admin-job-notice">{{ adminJobNotice }}</p>

        <div class="controls-row">
          <div v-if="tab === 'appointments'" class="subtabs" style="margin-bottom: 0;">
            <a
              href="#"
              class="subtab-btn"
              :class="{ active: appt_tab === 'upcoming' }"
              @click.prevent="appt_tab = 'upcoming'"
            >
              Upcoming
            </a>
            <a
              href="#"
              class="subtab-btn"
              :class="{ active: appt_tab === 'past' }"
              @click.prevent="appt_tab = 'past'"
            >
              Past
            </a>
          </div>

          <div class="search-wrapper">
            <form method="get" style="width: 100%; margin: 0;" @submit.prevent>
              <input v-model="search" type="text" name="search" class="pill-input" :placeholder="`Search ${tab}...`">
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

          <RouterLink v-if="tab === 'doctors'" to="/admin/create-doctor" class="add-button">Add New Doctor</RouterLink>
        </div>

        <template v-if="tab === 'doctors' || tab === 'patients'">
          <template v-if="(tab === 'doctors' ? doctors : patients).length">
            <div
              v-for="item in tab === 'doctors' ? doctors : patients"
              :key="item.uid"
              class="list-item"
              :class="{ 'blacklisted-row': item.blacklisted }"
            >
              <div class="list-avatar"></div>
              <div class="list-info">
                <h4>{{ item.name }} {{ item.blacklisted ? '(Blacklisted)' : '' }}</h4>
                <p class="list-subtext">{{ item.specialization || item.email || '—' }}</p>
              </div>
              <div class="list-actions">
                <a href="#" class="action-pill view" @click.prevent="openUser(item)">View</a>
                <a href="#" class="action-pill edit" @click.prevent="openUser(item)">Edit</a>

                <a
                  href="#"
                  class="action-pill"
                  :class="item.blacklisted ? 'unblacklist' : 'blacklist'"
                  @click.prevent="toggleBlacklist(item)"
                >
                  {{ item.blacklisted ? 'Un-blacklist' : 'Blacklist' }}
                </a>
              </div>
            </div>
          </template>
          <div v-else class="no-content-card"><p class="no-content-text">No {{ tab }} found.</p></div>
        </template>

        <template v-else-if="tab === 'appointments'">
          <template v-if="appointments.length">
            <div v-for="appt in appointments" :key="appt.aid" class="list-item">
              <div class="list-info">
                <h4>{{ appt.patient.name }} with {{ appt.doctor.name }}</h4>
                <p class="list-subtext">{{ formatDateTime(appt.appointment_datetime) }}</p>
              </div>
              <div class="list-actions">
                <a href="#" class="action-pill view" @click.prevent="openAppointment(appt)">Details</a>
              </div>
            </div>
          </template>
          <div v-else class="no-content-card">
            <p class="no-content-text">No {{ appt_tab || 'upcoming' }} appointments found.</p>
          </div>
        </template>
      </div>
    </div>

    <div class="divider-right"></div>

    <div class="details-panel" :class="{ open: selected_user || selected_appointment }">
      <template v-if="selected_user">
        <div class="panel-header">
          <h3>View or Edit {{ selected_user.f_rid === 3 ? 'Doctor' : 'Patient' }}</h3>
          <a href="#" class="close-panel-btn" @click.prevent="closePanel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </a>
        </div>

        <form @submit.prevent="saveSelectedUser">
          <div class="doctor-details">
            <div class="detail-row">
              <span class="detail-label">Name</span>
              <input
                v-model.trim="selected_user.name"
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
                v-model.trim="selected_user.email"
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
                v-model="selectedUserPassword"
                type="password"
                name="password"
                class="sidebar-input"
                placeholder="Unchanged"
                minlength="6"
                maxlength="120"
              >
            </div>

            <template v-if="selected_user.f_rid === 3">
              <div class="detail-row">
                <span class="detail-label">Experience (Yrs)</span>
                <input
                  v-model="selected_user.experience_years"
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
                  v-model.trim="selected_user.specialization"
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
                  v-model.trim="selected_user.department.name"
                  type="text"
                  name="dept"
                  class="sidebar-input"
                  placeholder="Exact Dept Name"
                  minlength="2"
                  maxlength="120"
                >
              </div>
            </template>

            <button type="submit" class="save-btn">Save Changes</button>
          </div>
        </form>

        <h4 style="margin: 2rem 0 0.5rem 0; font-size: 1rem; font-weight: 500;">Appointment History</h4>
        <template v-if="filtered_user_history.length">
          <div class="history-card">
            <div v-for="appt in filtered_user_history" :key="appt.aid" class="history-item">
              <div class="history-info">
                <h4>
                  {{ selected_user.f_rid === 3 ? 'Patient' : 'Doctor' }}:
                  {{ selected_user.f_rid === 3 ? appt.patient.name : appt.doctor.name }}
                </h4>
                <p class="history-meta">{{ formatHistoryDateTime(appt) }}</p>
                <p class="history-note">{{ appt.diagnosis || 'No notes' }}</p>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="no-content-card" style="margin-top: 1rem;"><p class="no-content-text">No appointment history.</p></div>
      </template>

      <template v-else-if="selected_appointment">
        <div class="panel-header">
          <h3>Appointment Details</h3>
          <a href="#" class="close-panel-btn" @click.prevent="closePanel">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </a>
        </div>

        <div class="doctor-details" style="margin-bottom: 1.5rem;">
          <div class="detail-row"><span class="detail-label">Date</span><span class="detail-value">{{ formatDate(selected_appointment.appointment_datetime) }}</span></div>
          <div class="detail-row"><span class="detail-label">Time</span><span class="detail-value">{{ formatTime(selected_appointment.appointment_datetime) }}</span></div>
          <div class="detail-row">
            <span class="detail-label">Status</span>
            <span class="detail-value" style="text-transform: capitalize;">{{ selected_appointment.status }}</span>
          </div>
          <br>
          <div class="detail-row"><span class="detail-label">Doctor</span><span class="detail-value">{{ selected_appointment.doctor.name }}</span></div>
          <div class="detail-row"><span class="detail-label">Patient</span><span class="detail-value">{{ selected_appointment.patient.name }}</span></div>
        </div>

        <form @submit.prevent="saveSelectedAppointment">
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
          <button type="submit" class="submit-button">
            {{ selected_appointment.status === 'completed' ? 'Update Details' : 'Mark as Completed' }}
          </button>
        </form>

        <form v-if="isFutureAppointment(selected_appointment)" @submit.prevent="cancelSelectedAppointment">
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
  margin-top: auto;
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
  transition: width 0.12s linear;
  position: relative;
  z-index: 5;
  flex: 1;
}
.right.panel-open {
  width: 44%;
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

.section-container {
  background: white;
  padding: 1.5rem;
  margin-bottom: 1rem;
}

.stats-grid {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.stat-card {
  flex: 1;
  background: #f1f1f1;
  border-radius: 1.5rem;
  padding: 1.5rem;
  text-decoration: none;
  color: inherit;
  transition: background-color 0.2s, color 0.2s;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-start;
  min-height: 110px;
}
.stat-card:hover {
  background: #e9ecef;
}
.stat-card.active {
  background: #535353;
  color: white;
}
.stat-card h4 {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
  opacity: 0.8;
  line-height: 1.2;
}
.stat-card .stat-number {
  font-size: 3rem;
  font-weight: 600;
  line-height: 1;
  margin: 0;
}

.analytics-row {
  display: grid;
  grid-template-columns: 1.15fr 1.15fr 0.7fr;
  gap: 1rem;
  margin-bottom: 1.1rem;
  align-items: end;
}

.analytics-card {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
}

.analytics-header h4 {
  margin: 0 0 0.4rem 0;
  font-size: 0.9rem;
  font-weight: 500;
  color: #303846;
}

.analytics-demand .analytics-header h4 {
  text-align: center;
}

.analytics-canvas-wrap {
  position: relative;
  height: 124px;
}

.analytics-summary {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.analytics-summary-body {
  min-height: 124px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.35rem;
}

.analytics-summary-number {
  font-size: 2rem;
  font-weight: 600;
  line-height: 1;
  color: #535353;
}

.analytics-summary-meta {
  color: #5f6c7b;
  font-size: 0.88rem;
}

.analytics-summary-list {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  color: #7a8696;
  font-size: 0.82rem;
}

.job-notice {
  margin: 0 0 1rem 0;
  font-size: 0.88rem;
  line-height: 1.4;
  color: #7b8794;
}

.admin-job-notice {
  margin-top: 0.5rem;
  margin-bottom: 1.35rem;
}

.controls-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
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

.add-button {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 0 1.8rem;
  height: 50px;
  display: flex;
  align-items: center;
  border-radius: 5rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  text-decoration: none;
  flex-shrink: 0;
  transition: background-color 0.2s;
}
.add-button:hover {
  background-color: #0056b3;
}

.subtabs {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
}
.subtab-btn {
  background: #e9ecef;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 1rem;
  cursor: pointer;
  font-weight: 500;
  text-decoration: none;
  color: inherit;
  transition: background-color 0.2s, color 0.2s;
  white-space: nowrap;
}
.subtab-btn.active {
  background: #535353;
  color: white;
}

.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: none;
  transition: opacity 0.2s;
}
.list-item.blacklisted-row {
  opacity: 0.6;
}
.list-item.blacklisted-row:hover {
  opacity: 1;
}

.list-avatar {
  width: 40px;
  height: 40px;
  background: #7c7c7c;
  border-radius: 50%;
  flex-shrink: 0;
}
.list-info {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
.list-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
  font-weight: 500;
}
.list-subtext {
  margin: 0;
  color: #666;
  font-size: 0.9rem;
}
.list-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}
.action-pill {
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
  transition: background-color 0.2s;
}
.action-pill:hover {
  background: #dee2e6;
}
.action-pill.view,
.action-pill.edit {
  background: #e9ecef;
  color: inherit;
}
.action-pill.blacklist {
  background: #e9ecef;
  color: #dc3545;
}
.action-pill.unblacklist {
  background: #e9ecef;
  color: #28a745;
}

.no-content-card {
  background: #f1f1f1;
  border-radius: 1rem;
  padding: 1rem;
  margin-bottom: 1rem;
  text-align: center;
}
.no-content-text {
  margin: 0;
  color: #686868;
}

.details-panel {
  width: 0;
  padding: 0;
  overflow: hidden;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  transition: width 0.12s linear, padding 0.12s linear;
  z-index: 0;
  flex-shrink: 0;
  min-width: 0;
}
.details-panel.open {
  width: 36%;
  padding: 1.5rem;
  overflow-y: auto;
}
.panel-header {
  font-size: 1.2rem;
  font-weight: 500;
  margin: 0 0 1.5rem 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 500;
  line-height: 1.2;
}
.close-panel-btn {
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
.close-panel-btn:hover {
  background: #dee2e6;
  color: #000;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
  padding-bottom: 0.8rem;
}
.detail-row:last-of-type {
  margin-bottom: 0;
}
.detail-label {
  font-weight: 500;
  color: #666;
  flex-shrink: 0;
}
.detail-value {
  font-weight: 500;
  text-align: right;
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
  font-family: inherit;
}
textarea::placeholder {
  color: rgb(0 0 0 / 50%);
  font-size: 1rem;
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

.save-btn,
.submit-button {
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
.save-btn:hover,
.submit-button:hover {
  background: #d0e4ff;
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
.cancel-button:hover {
  background: #e2e6ea;
}

.history-card {
  background: #f1f1f1;
  border-radius: 1rem;
  padding: 1rem;
  padding-bottom: 0.7rem;
  margin-top: 1rem;
}
.history-item {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
}
.history-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
}
.history-item h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
}
.history-meta,
.history-note {
  margin: 0 0 0.25rem 0;
  color: #666;
  font-size: 0.9rem;
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
  }
  .right {
    width: 100%;
    height: auto;
    min-height: auto;
  }
  .right.panel-open {
    width: 100%;
  }
  .details-panel {
    width: 100%;
    position: static;
    height: auto;
  }
  .details-panel:not(.open) {
    width: 0;
    padding: 0;
  }
  .divider-right {
    display: none !important;
  }
  .stats-grid {
    flex-direction: column;
    align-items: stretch;
  }
  .analytics-row {
    grid-template-columns: 1fr;
  }
  .controls-row,
  .list-item {
    flex-direction: column;
    align-items: stretch;
  }
  .add-button {
    width: 100%;
    justify-content: center;
  }
  .list-actions {
    width: 100%;
  }
  .action-pill {
    flex: 1;
  }
}
</style>
