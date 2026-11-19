import type { TrafficLightColor } from '@/types/api'

export type TrafficLightBadgeVariant = 'success' | 'warning' | 'danger'

export interface TrafficLightMetaItem {
  badgeVariant: TrafficLightBadgeVariant
  label: string
  shortTitle: string
}

/**
 * Canonical Russian presentation metadata for traffic-light verdicts.
 */
export const TRAFFIC_LIGHT_META: Record<TrafficLightColor, TrafficLightMetaItem> = {
  green: {
    badgeVariant: 'success',
    label: 'Можно брать',
    shortTitle: 'Рекомендуется к покупке',
  },
  yellow: {
    badgeVariant: 'warning',
    label: 'Под вопросом',
    shortTitle: 'Требует проверки сметы и рисков',
  },
  red: {
    badgeVariant: 'danger',
    label: 'Высокий риск',
    shortTitle: 'Покупка не рекомендуется',
  },
}
