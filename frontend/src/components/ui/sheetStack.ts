import { ref } from 'vue'

const openSheetStack = ref<symbol[]>([])

export function registerOpenSheet(token: symbol): void {
  if (!openSheetStack.value.includes(token)) {
    openSheetStack.value = [...openSheetStack.value, token]
  }
}

export function unregisterOpenSheet(token: symbol): void {
  if (openSheetStack.value.includes(token)) {
    openSheetStack.value = openSheetStack.value.filter((item) => item !== token)
  }
}

export function getSheetStackIndex(token: symbol): number {
  return openSheetStack.value.indexOf(token)
}

export function isTopMostOpenSheet(token: symbol): boolean {
  const stack = openSheetStack.value
  return stack.length > 0 && stack[stack.length - 1] === token
}
