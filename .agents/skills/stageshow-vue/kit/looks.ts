import { inject, provide, shallowRef, computed, reactive, type InjectionKey, type Ref } from 'vue'

// The look a stage sets for everything inside it: theme, palette, fidelity,
// and which of its designs (wide or compact) is showing. <Stage> provides it;
// parts read it with useLook().

/** glass: frosted, translucent surfaces over a soft color field. */
export type Theme = 'light' | 'dark' | 'blueprint' | 'glass'
export type Palette = 'accent' | 'mono'
/** minimal: no text, only shapes. standard: real text where it carries meaning. realistic: real text, logos and avatars everywhere. */
export type Fidelity = 'minimal' | 'standard' | 'realistic'
/** wide: the design size. compact: the smaller design used below `compact.below`. */
export type Layout = 'wide' | 'compact'

export type Look = {
  theme: Theme
  palette: Palette
  fidelity: Fidelity
  layout: Layout
}

export const defaultLook: Look = {
  theme: 'light',
  palette: 'accent',
  fidelity: 'standard',
  layout: 'wide',
}

export const LookSymbol: InjectionKey<Ref<Look>> = Symbol('StageLook')

export function provideLook(look: Ref<Look>) {
  provide(LookSymbol, look)
}

export type UseLookReturn = Look & { readonly value: Look }

export function useLook(): UseLookReturn {
  const lookRef = inject(LookSymbol, shallowRef(defaultLook))
  return reactive({
    get theme() {
      return lookRef.value.theme
    },
    get palette() {
      return lookRef.value.palette
    },
    get fidelity() {
      return lookRef.value.fidelity
    },
    get layout() {
      return lookRef.value.layout
    },
    get value() {
      return lookRef.value
    },
  }) as UseLookReturn
}
