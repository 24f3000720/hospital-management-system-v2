<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const deferredInstallPrompt = ref(null)

function handleBeforeInstallPrompt(event) {
  event.preventDefault()
  deferredInstallPrompt.value = event
}

function handleAppInstalled() {
  deferredInstallPrompt.value = null
}

async function installApp() {
  if (!deferredInstallPrompt.value) return

  deferredInstallPrompt.value.prompt()
  await deferredInstallPrompt.value.userChoice
  deferredInstallPrompt.value = null
}

onMounted(() => {
  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
  window.addEventListener('appinstalled', handleAppInstalled)
})

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
  window.removeEventListener('appinstalled', handleAppInstalled)
})
</script>

<template>
  <RouterView />
  <button
    v-if="deferredInstallPrompt"
    type="button"
    class="install-app-button"
    @click="installApp"
  >
    Add to Desktop
  </button>
</template>

<style scoped>
.install-app-button {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  z-index: 1000;
  border: none;
  border-radius: 999px;
  background: #f1f4f8;
  color: #005eff;
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 6px 20px rgb(0 0 0 / 10%);
}

@media (max-width: 768px) {
  .install-app-button {
    right: 0.75rem;
    bottom: 0.75rem;
    padding: 0.7rem 0.95rem;
  }
}
</style>
