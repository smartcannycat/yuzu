<script setup lang="ts">
import { Stage, Phone, LockScreen, Notification, Bar, WALLPAPER } from '../../kit'
import { mail } from '../../assets/app-icons'

// Every phone frame in the kit, at the same width. Narrow, a 150 phone's
// notification can't be read, so each frame is drawn at 300 and cropped to
// the half that shows it: the notification and the frame's bottom corners
// (the top, for the frames with an app on screen).

const WALL = WALLPAPER
const FRAMES = ['pro', 'silver', 'bezel', 'android', 'soft', 'clay', 'outline', 'bare'] as const
</script>

<template>
  <Stage specimen :width="720" :height="860" :compact="{ below: 600, width: 358, height: 2862 }" v-slot="{ layout }">
    <div
      :style="{
        display: 'grid',
        gridTemplateColumns: layout === 'compact' ? '300px' : 'repeat(4, 150px)',
        justifyContent: 'space-between',
        rowGap: '28px',
        padding: layout === 'compact' ? '16px' : '28px',
        background: 'var(--ss-well)',
        height: '100%',
      }"
    >
      <div
        v-for="frame in FRAMES"
        :key="frame"
        :style="{
          display: 'grid',
          gap: '10px',
          justifyItems: 'center',
          font: '500 12px system-ui',
          color: 'var(--ss-text)',
        }"
      >
        <div
          v-if="layout === 'compact'"
          :style="{
            display: 'flex',
            alignItems: frame === 'soft' || frame === 'outline' ? 'flex-start' : 'flex-end',
            height: '300px',
            overflow: 'hidden',
            paddingBottom: frame === 'soft' || frame === 'outline' ? '0px' : '12px',
          }"
        >
          <Phone
            :width="300"
            :frame="frame"
            :dark="frame !== 'soft' && frame !== 'outline'"
            :wallpaper="frame === 'soft' || frame === 'outline' ? undefined : WALL"
          >
            <div v-if="frame === 'soft' || frame === 'outline'" :style="{ display: 'grid', gap: '14px', padding: '72px 28px' }">
              <div :style="{ width: '96px', height: '96px', borderRadius: '20px', background: '#f1f2f6', justifySelf: 'center' }" />
              <div :style="{ font: '500 22px system-ui', textAlign: 'center', color: '#55607a' }">Oak dining chair</div>
              <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px' }">
                <div :style="{ height: '64px', borderRadius: '14px', background: '#000' }" />
                <div :style="{ height: '64px', borderRadius: '14px', background: '#00d66f' }" />
              </div>
              <Bar v-for="(w, i) in [70, 52, 64]" :key="i" :w="`${w}%`" :h="14" :r="7" :tone="2" />
            </div>
            <LockScreen v-else>
              <Notification title="Payment received" body="$249.00 from Jackson Hot Yoga">
                <template #icon>
                  <img :src="mail" alt="" />
                </template>
              </Notification>
            </LockScreen>
          </Phone>
        </div>
        <Phone
          v-else
          :width="150"
          :frame="frame"
          :dark="frame !== 'soft' && frame !== 'outline'"
          :wallpaper="frame === 'soft' || frame === 'outline' ? undefined : WALL"
        >
          <div v-if="frame === 'soft' || frame === 'outline'" :style="{ display: 'grid', gap: '14px', padding: '72px 28px' }">
            <div :style="{ width: '96px', height: '96px', borderRadius: '20px', background: '#f1f2f6', justifySelf: 'center' }" />
            <div :style="{ font: '500 22px system-ui', textAlign: 'center', color: '#55607a' }">Oak dining chair</div>
            <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px' }">
              <div :style="{ height: '64px', borderRadius: '14px', background: '#000' }" />
              <div :style="{ height: '64px', borderRadius: '14px', background: '#00d66f' }" />
            </div>
            <Bar v-for="(w, i) in [70, 52, 64]" :key="i" :w="`${w}%`" :h="14" :r="7" :tone="2" />
          </div>
          <LockScreen v-else>
            <Notification title="Payment received" body="$249.00 from Jackson Hot Yoga">
              <template #icon>
                <img :src="mail" alt="" />
              </template>
            </Notification>
          </LockScreen>
        </Phone>
        {{ frame }}
      </div>
    </div>
  </Stage>
</template>
