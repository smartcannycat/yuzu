import { PRESET_CONFIGS_EXTRA } from '@/api/mock/lotDetailsPresetsExtra'
import { PRESET_CONFIGS_RISK } from '@/api/mock/lotDetailsPresetsRisk'
import { PRESET_CONFIGS_SAFE } from '@/api/mock/lotDetailsPresetsSafe'
import { PANEL_LABELS_RU, type PresetDetailConfig } from '@/api/mock/lotDetailsPresetTypes'

export { PANEL_LABELS_RU, type PresetDetailConfig }

export const PRESET_CONFIGS: Record<string, PresetDetailConfig> = {
  ...PRESET_CONFIGS_SAFE,
  ...PRESET_CONFIGS_RISK,
  ...PRESET_CONFIGS_EXTRA,
}
