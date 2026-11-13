import { createApp } from 'vue'
import Viewer from './Viewer.vue'

export function mount() {
  createApp(Viewer).mount('#root')
}
