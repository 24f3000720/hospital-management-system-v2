<script setup>
import { reactive } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { projectMeta } from '../constants/projectMeta'
import { useAuthStore } from '../stores/auth'

const form = reactive({
  name: '',
  email: '',
  password: '',
})

const router = useRouter()
const authStore = useAuthStore()

async function handleSubmit() {
  if (!form.name.trim() || !form.email.trim() || !form.password) {
    window.alert('Please fill in all required registration details.')
    return
  }

  try {
    await authStore.register({ ...form })
    window.alert('Registration successful. Please sign in with your new account.')
    await router.push({ name: 'signin' })
  } catch (error) {
    window.alert(error.message || 'Unable to register right now.')
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="container">
      <div class="left">
        <div class="sidebar-header">{{ projectMeta.title }}</div>

        <div class="sidebar-footer">
          <div>
            <div class="builder-label">Built by</div>
            <div class="builder-name">{{ projectMeta.builder }}</div>
          </div>
          <div class="project-purpose">
            {{ projectMeta.purpose }}
          </div>
        </div>
      </div>

      <div class="divider"></div>

      <div class="right">
        <div class="signup-container">
          <h2>Create a new account<br>as a Patient</h2>
          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <input
                v-model.trim="form.name"
                type="text"
                name="name"
                placeholder="Full Name"
                minlength="2"
                maxlength="120"
                required
              >
            </div>
            <div class="form-group">
              <input
                v-model.trim="form.email"
                type="email"
                name="email"
                placeholder="Email Address"
                autocomplete="email"
                maxlength="120"
                required
              >
            </div>
            <div class="form-group">
              <input
                v-model="form.password"
                type="password"
                name="password"
                placeholder="Password"
                autocomplete="new-password"
                minlength="6"
                maxlength="120"
                required
              >
            </div>
            <button type="submit" class="submit-button">Sign Up</button>
          </form>
          <RouterLink to="/signin" class="submit-alt">Already have an account? Sign In</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  margin: 0;
  padding: 0;
  background: #ffffff;
  color: #000;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
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
  width: 25%;
  padding: 1.5rem;
  box-sizing: border-box;
  background: #f8f9fa;
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
  margin: 0;
  line-height: 1.2;
  color: #000;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.builder-label {
  font-size: 0.8rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.builder-name {
  font-size: 1rem;
  font-weight: 500;
  color: #000;
  margin-bottom: 0.5rem;
}

.project-purpose {
  font-size: 0.9rem;
  color: #555;
  line-height: 1.4;
}

.divider {
  width: 1px;
  background: #e5e7eb;
  flex-shrink: 0;
}

.right {
  flex: 1;
  box-sizing: border-box;
  background: white;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100vh;
  padding: 2rem;
  overflow-y: auto;
}

form {
  display: block;
  width: 100%;
}

.signup-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0;
  max-width: 420px;
  width: 100%;
  box-sizing: border-box;
}

.signup-container h2 {
  margin: 0 0 1.5rem 0;
  font-size: 1.5rem;
  font-weight: 500;
  text-align: left;
  width: 100%;
  line-height: 1.2;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
  width: 100%;
}

input[type='text'],
input[type='email'],
input[type='password'] {
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
  font-family: inherit;
}

input:focus {
  border-color: #005eff;
}

input::placeholder {
  color: rgb(0 0 0 / 50%);
  font-size: 1rem;
}

.submit-button,
.submit-alt {
  width: 100%;
  border: none;
  padding: 0.8rem 1rem;
  font-size: 0.85rem;
  font-weight: 500;
  border-radius: 10rem;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: 0.5rem;
  box-sizing: border-box;
  line-height: 1.2;
  display: block;
  text-align: center;
  text-decoration: none;
}

.submit-button {
  background: #005eff;
  color: white;
}

.submit-button:hover {
  background: #0046c0;
}

.submit-alt {
  background: #e7f1ff;
  color: #005eff;
}

.submit-alt:hover {
  background: #d0e4ff;
}

@media (max-width: 900px) {
  .container {
    flex-direction: column;
  }

  .left {
    width: 100%;
    height: auto;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .sidebar-footer {
    margin-top: 1.5rem;
  }

  .divider {
    display: none;
  }

  .right {
    height: auto;
    min-height: 60vh;
    padding: 1.5rem;
  }
}
</style>
