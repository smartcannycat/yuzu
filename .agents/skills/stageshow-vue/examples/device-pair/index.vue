<script setup lang="ts">
import { Badge, Bar, Chart, Icon, LockScreen, Notification, Phone, Stage, Text, Window, WALLPAPER } from '../../kit'
import './payments.css'

// "Get paid anywhere": a device pair. The dashboard is pinned top-left and
// runs off the bottom; the phone straddles its right edge over empty margin
// and placeholder rows, so the revenue figure and its chart stay clear. Real words:
// Revenue, the total, the change, and the notification. Narrow, the sidebar
// goes and both devices keep their true size: the window runs off the right,
// the phone stands a gutter in from it, whole across, its notification whole.

const REVENUE = [18, 22, 20, 27, 25, 31, 29, 36, 34, 41, 39, 47]

const ROWS = [
  { name: 74, amount: 40 },
  { name: 58, amount: 46 },
  { name: 82, amount: 36 },
  { name: 64, amount: 44 },
  { name: 70, amount: 38 },
]

const WALL = WALLPAPER
</script>

<template>
  <Stage :width="640" :height="400" :compact="{ below: 600, width: 358, height: 400 }" class="ps-section">
    <Window url="dashboard.northwind.co" class="ps-window">
      <aside class="ps-sidebar">
        <span class="ps-logo">Northwind</span>
        <div v-for="(w, i) in [46, 58, 40, 52, 36]" :key="i" class="ps-nav" :data-active="i === 0 || undefined">
          <Bar :w="10" :h="10" :r="3" :tone="i === 0 ? 4 : 2" />
          <Bar :w="w" :h="5" :tone="i === 0 ? 4 : 2" />
        </div>
      </aside>

      <div class="ps-main">
        <div class="ps-top">
          <section class="ps-revenue">
            <div class="ps-head">
              <Text class="ps-label">Revenue</Text>
              <Bar :w="48" :h="18" :r="5" :tone="1" />
            </div>
            <div class="ps-figure">
              <Text class="ps-total">$12,604.80</Text>
              <Badge tone="success">+12.4%</Badge>
            </div>
            <Bar :w="72" :h="5" :tone="2" />
            <Chart :data="REVENUE" :width="224" :height="88" class="ps-chart" />
            <div class="ps-axis">
              <Bar :w="22" :h="4" :tone="1" />
              <Bar :w="22" :h="4" :tone="1" />
            </div>
          </section>
        </div>

        <div class="ps-list">
          <Bar :w="64" :h="6" :tone="3" :style="{ marginBottom: '10px' }" />
          <div v-for="(row, i) in ROWS" :key="i" class="ps-row">
            <Bar :w="16" :h="16" :r="5" :tone="2" />
            <Bar :w="row.name" :tone="3" />
            <Bar :w="row.amount" :tone="2" :style="{ marginLeft: 'auto' }" />
          </div>
        </div>
      </div>
    </Window>

    <Phone :width="236" frame="pro" dark :wallpaper="WALL" class="ps-phone">
      <LockScreen size="satellite" stack="top">
        <!-- The product's own app sends it: the dashboard's bolt, not Mail -->
        <Notification title="Payment received" body="$249.00 from Oak & Ivy">
          <template #icon>
            <Icon name="bolt" filled :size="20" />
          </template>
        </Notification>
      </LockScreen>
    </Phone>
  </Stage>
</template>
