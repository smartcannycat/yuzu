export { default as Phone } from './Phone.vue'
export type { PhoneProps, PhoneFrame } from './Phone.vue'
export { default as LockScreen } from './LockScreen.vue'
export type { LockScreenProps } from './LockScreen.vue'
export { default as Notification } from './Notification.vue'
export type { NotificationProps } from './Notification.vue'

/** The default lock screen wallpaper: a soft blue to lilac gradient with a
 * faint light at the top, after the iPhone's own defaults. Quiet enough to
 * sit behind any demo; white type and frosted banners read on it. */
export const WALLPAPER =
  'radial-gradient(120% 70% at 25% 0%, rgba(255, 255, 255, 0.3), transparent 65%), linear-gradient(172deg, #8ea9d6 0%, #9aa1d4 50%, #aca3cf 100%)'
