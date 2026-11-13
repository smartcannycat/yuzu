<script setup lang="ts">
import { Bar, Stage, Text, Window, Row, Avatar } from '../../kit'
import './card.css'

// A feature card (400 × 300) with the product masked inside it: the window is
// pinned top-left, runs off the right and bottom, and a detail card straddles
// its left edge over the sidebar, about half outside. Real words only on the
// selected customer, its neighbors and the total; bars everywhere else.

const ROWS: { selected?: boolean; name?: number | string; amount?: number | string }[] = [
  { name: 'Halvorsen & Co', amount: '$1,240' },
  { selected: true },
  { name: 'Lumen Studio', amount: '$860' },
  { name: 84, amount: 38 },
  { name: 64, amount: 48 },
  { name: 78, amount: 40 },
]
const NAV = ['Overview', 'Customers', 'Invoices', 'Reports']
</script>

<template>
  <Stage :width="400" :height="300" :compact="{ below: 400, width: 358, height: 300 }" class="sc-card">
    <Window url="dashboard.northwind.co" class="sc-window">
      <!-- The sidebar is what the detail card covers, so the rows stay readable -->
      <aside class="sc-sidebar">
        <Bar :w="20" :h="20" :r="6" :tone="4" style="margin-bottom: 10px;" />
        <div v-for="(label, i) in NAV" :key="i" class="sc-nav" :data-on="i === 1 || undefined">
          <Bar :w="10" :h="10" :r="3" :tone="i === 1 ? 4 : 3" />
          <Text class="sc-nav__label">{{ label }}</Text>
        </div>
      </aside>
      <div class="sc-main">
        <div class="sc-header">
          <Text class="sc-title">Customers</Text>
          <Bar :w="52" :h="22" :r="6" :tone="2" />
        </div>
        <div class="sc-list">
          <template v-for="(row, i) in ROWS" :key="i">
            <Row v-if="row.selected" :pad="0" selected class="sc-row" data-target="selected">
              <template #lead>
                <Avatar name="Jackson Hot Yoga" tone="accent" :size="18" />
              </template>
              <template #title>
                <Text class="sc-name">Jackson Hot Yoga</Text>
              </template>
              <Bar :w="40" :tone="4" />
            </Row>
            <Row v-else :pad="0" class="sc-row">
              <template #lead>
                <Bar :w="18" :h="18" :r="9" :tone="2" />
              </template>
              <template #title>
                <Text v-if="typeof row.name === 'string'" class="sc-rowname">{{ row.name }}</Text>
                <Bar v-else :w="row.name!" :tone="3" />
              </template>
              <Text v-if="typeof row.amount === 'string'" class="sc-rowamount">{{ row.amount }}</Text>
              <Bar v-else :w="row.amount!" :tone="2" />
            </Row>
          </template>
        </div>
      </div>
    </Window>

    <div class="sc-detail">
      <div class="sc-detail-head">
        <Avatar name="Jackson Hot Yoga" tone="accent" :size="26" class="sc-avatar-large" />
        <div class="sc-detail-who">
          <Text class="sc-detail-name">Jackson Hot Yoga</Text>
          <Bar :w="64" :h="5" :tone="2" />
        </div>
      </div>
      <div v-for="(w, i) in [48, 36]" :key="i" class="sc-detail-row">
        <Bar :w="w" :h="5" :tone="3" />
        <Bar :w="w - 12" :h="5" :tone="2" />
      </div>
      <div class="sc-detail-row total">
        <Text class="sc-detail-label">Total</Text>
        <Text class="sc-detail-total">$72.00</Text>
      </div>
    </div>
  </Stage>
</template>
