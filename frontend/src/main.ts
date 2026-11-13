import { createPinia } from 'pinia'
import { createApp } from 'vue'

import { setUnauthorizedHandler } from '@/api'
import App from '@/App.vue'

import '@/assets/main.css'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

setUnauthorizedHandler(() => {
  const authStore = useAuthStore(pinia)
  authStore.logout()
  const current = router.currentRoute.value
  if (current.meta.requiresAuth) {
    void router.replace({
      name: 'auth',
      query: current.fullPath !== '/' ? { redirect: current.fullPath } : undefined,
    })
  }
})

app.mount('#app')
