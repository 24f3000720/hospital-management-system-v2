<script setup>
import { RouterLink } from 'vue-router'

import { projectMeta } from '../constants/projectMeta'
</script>

<template>
  <div class="landing-page">
    <div class="landing-container">
      <h1>Welcome to {{ projectMeta.title }}</h1>
      <p>Your portal for patient registration, doctor management, and admin oversight.</p>
      <div class="landing-actions">
        <RouterLink to="/signin" class="submit-alt">Sign In</RouterLink>
        <RouterLink to="/signup" class="submit-alt">Sign Up</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.landing-page {
  margin: 0;
  padding: 0;
  background: #ffffff;
  color: #000;
  font-family: sans-serif;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  user-select: none;
}

.landing-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem;
  max-width: 500px;
  width: 100%;
  box-sizing: border-box;
  text-align: center;
}

.landing-container h1 {
  font-size: 2.5rem;
  font-weight: 500;
  margin: 0 0 1rem 0;
}

.landing-container p {
  font-size: 1.1rem;
  margin: 0 0 2rem 0;
  color: #666;
}

.landing-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 1rem;
}

.submit-alt {
  display: inline-block;
  background: rgba(0, 0, 0, 0.1);
  border: none;
  padding: 0.8rem 2rem;
  color: #005eff;
  font-size: 0.85rem;
  font-weight: 500;
  border-radius: 10rem;
  cursor: pointer;
  transition: all 0.3s ease;
  text-decoration: none;
  margin: 0 0.5rem;
}

.submit-alt:hover {
  background: rgba(0, 0, 0, 0.05);
}

@media (max-width: 768px) {
  .landing-container {
    padding: 1rem;
  }

  .landing-container h1 {
    font-size: 2rem;
  }
}
</style>
