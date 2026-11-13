import { createApp, defineComponent, h, onErrorCaptured, ref } from 'vue'
import { StillSymbol } from '../kit/reduced-motion'
import './preview.css'

const vueModules = import.meta.glob<any>('../examples/*/index.vue')
const tsModules = import.meta.glob<any>('../examples/*/index.ts')
const teachingModules = import.meta.glob<any>('../teaching/contrasts.{vue,ts}')

let currentApp: any = null

export async function mount(name: string, still: boolean, onError: (message: string) => void = () => {}) {
  if (currentApp) {
    currentApp.unmount()
    currentApp = null
  }

  const load =
    name === 'contrasts'
      ? teachingModules['../teaching/contrasts.vue'] || teachingModules['../teaching/contrasts.ts']
      : vueModules[`../examples/${name}/index.vue`] || tsModules[`../examples/${name}/index.ts`]

  if (!load) throw new Error(`Unknown example: ${name}`)
  const mod = await load()
  const Demo = mod.default || mod

  const Boundary = defineComponent({
    props: {
      onError: { type: Function, default: () => {} },
    },
    setup(props, { slots }) {
      const errorMsg = ref<string | null>(null)
      onErrorCaptured((err: Error) => {
        errorMsg.value = err.message
        props.onError(err.message)
        return false
      })
      return () => {
        if (errorMsg.value) {
          return h('p', { role: 'alert' }, `This example could not render: ${errorMsg.value}. Check the console for details, then replay after fixing it.`)
        }
        return slots.default ? slots.default() : null
      }
    },
  })

  const RootWrapper = defineComponent({
    setup() {
      return () => h('div', { id: 'example' }, [
        h(Boundary, { onError }, {
          default: () => h(Demo),
        }),
      ])
    },
  })

  const rootEl = document.getElementById('root')!
  rootEl.innerHTML = ''
  currentApp = createApp(RootWrapper)
  currentApp.provide(StillSymbol, ref(still))
  currentApp.mount(rootEl)
}
