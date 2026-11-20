import { AlertTriangle, CheckCircle2, OctagonAlert } from '@lucide/vue'

import type { TrafficLightColor } from '@/types/api'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'

export const TRAFFIC_LIGHT_COLORS: readonly TrafficLightColor[] = ['green', 'yellow', 'red']

export const VERDICT_ICON_MAP: Record<TrafficLightColor, typeof CheckCircle2> = {
  green: CheckCircle2,
  yellow: AlertTriangle,
  red: OctagonAlert,
}

const TOOLBAR_ACTIVE_CLASSES: Record<TrafficLightColor, string> = {
  green: 'bg-success-bg text-success shadow-segment',
  yellow: 'bg-warning-bg text-warning shadow-segment',
  red: 'bg-danger-bg text-danger shadow-segment',
}

const FILTER_ACTIVE_CLASSES: Record<TrafficLightColor, string> = {
  green: 'bg-success-bg text-success border-success/30',
  yellow: 'bg-warning-bg text-warning border-warning/30',
  red: 'bg-danger-bg text-danger border-danger/30',
}

export interface VerdictOptionItem {
  value: TrafficLightColor
  label: string
  count: number
  icon: typeof CheckCircle2
  activeClass: string
}

export function buildVerdictOptionItems(
  countsByVerdict: Partial<Record<TrafficLightColor, number>>,
  variant: 'toolbar' | 'filter',
): VerdictOptionItem[] {
  const classMap = variant === 'toolbar' ? TOOLBAR_ACTIVE_CLASSES : FILTER_ACTIVE_CLASSES
  return TRAFFIC_LIGHT_COLORS.map((color) => ({
    value: color,
    label: TRAFFIC_LIGHT_META[color].label,
    count: countsByVerdict[color] ?? 0,
    icon: VERDICT_ICON_MAP[color],
    activeClass: classMap[color],
  }))
}
