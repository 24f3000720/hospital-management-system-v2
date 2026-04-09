<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { createDummyPayment, getPatientPayments, getPatientProfile } from '../services/patientService'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const state = reactive({
  currentUser: null,
  payments: [],
})

const selectedItem = ref(null)
const paymentForm = reactive({
  card_holder: '',
  card_number: '',
  expiry: '',
  cvv: '',
})

const jinjaemail = computed(() => state.currentUser?.email || '')
const pendingPayments = computed(() => state.payments.filter((item) => !item.payment))
const paidPayments = computed(() => state.payments.filter((item) => Boolean(item.payment)))
const allPaymentItems = computed(() => [...pendingPayments.value, ...paidPayments.value])
const selectedAmount = computed(() => selectedItem.value?.amount_due || 0)
const selectedIsPaid = computed(() => Boolean(selectedItem.value?.payment))

function resetPaymentForm() {
  paymentForm.card_holder = state.currentUser?.name || ''
  paymentForm.card_number = ''
  paymentForm.expiry = ''
  paymentForm.cvv = ''
}

function syncSelectedItem() {
  if (!allPaymentItems.value.length) {
    selectedItem.value = null
    return
  }

  if (!selectedItem.value) {
    selectedItem.value = allPaymentItems.value[0]
    resetPaymentForm()
    return
  }

  const updatedItem = allPaymentItems.value.find(
    (item) => item.appointment.aid === selectedItem.value.appointment.aid,
  )

  selectedItem.value = updatedItem || allPaymentItems.value[0]
}

async function loadProfile() {
  const response = await getPatientProfile()
  state.currentUser = response.data.patient
  if (!paymentForm.card_holder) {
    paymentForm.card_holder = response.data.patient.name || ''
  }
}

async function loadPayments() {
  const response = await getPatientPayments()
  state.payments = response.data.payments || []
  syncSelectedItem()
}

function selectItem(item) {
  selectedItem.value = item
  resetPaymentForm()
}

function formatDateTime(dateTime) {
  const value = dateTime || selectedItem.value?.appointment?.appointment_datetime
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).replace(',', ' •')
}

function statusLabel(item) {
  return item.payment ? 'Paid' : 'Pending Payment'
}

async function submitPayment() {
  if (!selectedItem.value || selectedItem.value.payment) return

  if (!paymentForm.card_holder.trim()) {
    window.alert('Card holder name is required.')
    return
  }

  try {
    await createDummyPayment({
      appointment_id: selectedItem.value.appointment.aid,
      card_holder: paymentForm.card_holder,
      card_number: paymentForm.card_number,
      expiry: paymentForm.expiry,
      cvv: paymentForm.cvv,
    })

    await loadPayments()
    window.alert('Dummy payment recorded successfully.')
  } catch (error) {
    window.alert(error.message || 'Unable to record payment.')
  }
}

async function handleLogout() {
  await authStore.logout()
  await router.push({ name: 'signin' })
}

onMounted(async () => {
  try {
    await authStore.initialize()
    await loadProfile()
    await loadPayments()
  } catch (error) {
    window.alert(error.message || 'Unable to load the payment portal.')
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

      <RouterLink to="/patient" class="sidebar-nav-link">Dashboard</RouterLink>
      <RouterLink to="/patient/payments" class="sidebar-nav-link active">Payments</RouterLink>
      <a href="#" class="logout" @click.prevent="handleLogout">Logout</a>
    </div>

    <div class="divider"></div>

    <div class="right" :class="{ 'panel-open': selectedItem }">
      <div class="section-container">
        <div class="section-header">
          <h3>Dummy Payment Portal</h3>
          <p>
            Pay for completed treatments here. This is a demo-only payment flow and no real money is charged.
          </p>
        </div>

        <div class="payment-group">
          <h4>Pending Payments</h4>
          <template v-if="pendingPayments.length">
            <div
              v-for="item in pendingPayments"
              :key="`pending-${item.appointment.aid}`"
              class="list-item"
              @click="selectItem(item)"
            >
              <div class="list-avatar"></div>
              <div class="list-info">
                <h4>{{ item.appointment.doctor.name }}</h4>
                <p class="list-subtext">{{ formatDateTime(item.appointment.completed_at || item.appointment.appointment_datetime) }}</p>
                <p class="list-subtext">Amount due: INR {{ item.amount_due }}</p>
              </div>
              <div class="list-actions">
                <span class="status-pill pending">{{ statusLabel(item) }}</span>
              </div>
            </div>
          </template>
          <div v-else class="empty-card">No pending treatment payments.</div>
        </div>

        <div class="payment-group">
          <h4>Paid Receipts</h4>
          <template v-if="paidPayments.length">
            <div
              v-for="item in paidPayments"
              :key="`paid-${item.appointment.aid}`"
              class="list-item"
              @click="selectItem(item)"
            >
              <div class="list-avatar"></div>
              <div class="list-info">
                <h4>{{ item.appointment.doctor.name }}</h4>
                <p class="list-subtext">{{ formatDateTime(item.payment.paid_at) }}</p>
                <p class="list-subtext">
                  Ref: {{ item.payment.payment_reference }} • Card ending {{ item.payment.card_last4 }}
                </p>
              </div>
              <div class="list-actions">
                <span class="status-pill paid">Paid</span>
              </div>
            </div>
          </template>
          <div v-else class="empty-card">No payment receipts yet.</div>
        </div>
      </div>
    </div>

    <div class="divider-right"></div>

    <div class="payment-panel" :class="{ open: selectedItem }">
      <template v-if="selectedItem">
        <div class="panel-header">
          <h3>{{ selectedIsPaid ? 'Payment Receipt' : 'Pay For Treatment' }}</h3>
        </div>

        <div class="detail-list">
          <div class="detail-row">
            <span class="detail-label">Doctor</span>
            <span class="detail-value">{{ selectedItem.appointment.doctor.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Appointment</span>
            <span class="detail-value">{{ formatDateTime(selectedItem.appointment.completed_at || selectedItem.appointment.appointment_datetime) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Diagnosis</span>
            <span class="detail-value">{{ selectedItem.appointment.diagnosis || 'N/A' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Amount</span>
            <span class="detail-value">INR {{ selectedAmount }}</span>
          </div>
        </div>

        <template v-if="selectedIsPaid">
          <div class="receipt-card">
            <div class="detail-row">
              <span class="detail-label">Status</span>
              <span class="detail-value">Paid</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Reference</span>
              <span class="detail-value">{{ selectedItem.payment.payment_reference }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Card</span>
              <span class="detail-value">Ending {{ selectedItem.payment.card_last4 }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Paid At</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.payment.paid_at) }}</span>
            </div>
          </div>
        </template>

        <form v-else class="payment-form" @submit.prevent="submitPayment">
          <div class="form-group">
            <label for="card_holder">Card Holder</label>
            <input
              id="card_holder"
              v-model.trim="paymentForm.card_holder"
              type="text"
              maxlength="120"
              required
            >
          </div>
          <div class="form-group">
            <label for="card_number">Card Number</label>
            <input
              id="card_number"
              v-model.trim="paymentForm.card_number"
              type="text"
              inputmode="numeric"
              maxlength="23"
              placeholder="1234 5678 9012 3456"
              required
            >
          </div>
          <div class="mini-grid">
            <div class="form-group">
              <label for="expiry">Expiry</label>
              <input
                id="expiry"
                v-model.trim="paymentForm.expiry"
                type="text"
                maxlength="5"
                placeholder="MM/YY"
                required
              >
            </div>
            <div class="form-group">
              <label for="cvv">CVV</label>
              <input
                id="cvv"
                v-model.trim="paymentForm.cvv"
                type="password"
                inputmode="numeric"
                maxlength="4"
                placeholder="123"
                required
              >
            </div>
          </div>
          <button type="submit" class="submit-button">Pay INR {{ selectedAmount }}</button>
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
  min-height: 100vh;
  width: 100%;
  background: white;
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
  flex-shrink: 0;
}
.sidebar-header {
  font-size: 1.2rem;
  font-weight: 500;
  margin: 0 0 1rem 0;
  line-height: 1.2;
}
.sidebar-name {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #666;
}
.sidebar-nav-link {
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  color: #333;
  align-self: flex-start;
  margin-bottom: 1rem;
}
.sidebar-nav-link:first-of-type {
  margin-top: auto;
}
.sidebar-nav-link.active,
.sidebar-nav-link:hover {
  color: #007bff;
}
.logout {
  color: #dc3545;
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  align-self: flex-start;
}
.divider,
.divider-right {
  width: 1px;
  background: #e5e7eb;
  flex-shrink: 0;
}
.right {
  width: 70%;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex: 1;
}
.right.panel-open {
  width: 70%;
}
.section-container {
  padding: 1.5rem;
}
.section-header {
  margin-bottom: 2rem;
}
.section-header h3 {
  margin: 0 0 0.6rem 0;
  font-size: 1.6rem;
  font-weight: 500;
}
.section-header p {
  margin: 0;
  color: #6f7c8a;
  line-height: 1.5;
}
.payment-group {
  margin-bottom: 2rem;
}
.payment-group h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 500;
}
.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  cursor: pointer;
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
  min-width: 0;
}
.list-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
}
.list-subtext {
  margin: 0;
  color: #666;
  font-size: 0.9rem;
}
.list-actions {
  flex-shrink: 0;
}
.status-pill {
  display: inline-block;
  border-radius: 999px;
  padding: 0.6rem 1rem;
  font-size: 0.85rem;
  font-weight: 500;
}
.status-pill.pending {
  background: #e7f1ff;
  color: #005eff;
}
.status-pill.paid {
  background: #edf6ef;
  color: #2f6a3b;
}
.empty-card {
  background: #f1f1f1;
  border-radius: 1rem;
  padding: 1rem;
  color: #686868;
}
.payment-panel {
  width: 0;
  padding: 0;
  overflow: hidden;
  box-sizing: border-box;
  background: white;
  transition: width 0.2s ease, padding 0.2s ease;
  flex-shrink: 0;
}
.payment-panel.open {
  width: 30%;
  padding: 1.5rem;
  overflow-y: auto;
}
.panel-header {
  margin: 0 0 1.5rem 0;
}
.panel-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 500;
}
.detail-list,
.receipt-card {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  margin-bottom: 1.5rem;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}
.detail-label {
  font-weight: 500;
  color: #666;
}
.detail-value {
  font-weight: 500;
  text-align: right;
}
.payment-form {
  margin-top: 1rem;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.form-group label {
  font-weight: 500;
  color: #666;
}
.form-group input {
  padding: 0.8rem 1rem;
  border: 1.5px solid rgb(0 0 0 / 15%);
  background: white;
  border-radius: 1rem;
  font-size: 0.95rem;
  font-family: inherit;
  outline: none;
}
.mini-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.submit-button {
  width: 100%;
  background: #e7f1ff;
  color: #007bff;
  border: none;
  padding: 0.85rem 1rem;
  border-radius: 6rem;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
}
.submit-button:hover {
  background: #d0e4ff;
}

@media (max-width: 768px) {
  .container {
    flex-direction: column;
  }
  .left,
  .right,
  .right.panel-open,
  .payment-panel,
  .payment-panel.open {
    width: 100%;
  }
  .payment-panel {
    padding: 0;
  }
  .payment-panel.open {
    padding: 1.5rem;
  }
  .divider,
  .divider-right {
    width: 100%;
    height: 1px;
  }
  .list-item,
  .detail-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .mini-grid {
    grid-template-columns: 1fr;
  }
}
</style>
