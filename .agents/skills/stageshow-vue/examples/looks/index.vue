<script setup lang="ts">
import { Badge, Field, Segmented, Stage, Text, Window } from '../../kit'
import { CanvasLook, ConsoleLook, FinanceLook, MessagesLook, ResearchLook } from './studies.vue'
import DimensionalLook from './skeuomorphic.vue'
import './radix.css'
import './looks.css'

// The same invitation in three product identities. Copy a look's tokens,
// then preserve the target product's typography and density, not this UI.

const looks = [
  ['look-default', 'Quiet workspace', 'System type · compact controls'],
  ['look-radix', 'Technical product', 'Indigo · precise borders'],
  ['look-consumer', 'Consumer app', 'Roomier controls · soft corners'],
] as const

const studies = [
  { look: 'look-console', title: 'Developer console', detail: 'Dark surfaces · restrained status', scene: ConsoleLook },
  { look: 'look-finance', title: 'Financial overview', detail: 'Tabular figures · measured hierarchy', scene: FinanceLook },
  { look: 'look-canvas', title: 'Creative workspace', detail: 'Open canvas · precise selection', scene: CanvasLook },
  { look: 'look-messages', title: 'Team conversation', detail: 'Soft surfaces · comfortable rhythm', scene: MessagesLook },
  { look: 'look-research', title: 'Research notebook', detail: 'Sans-serif reading · quiet structure', scene: ResearchLook },
  { look: 'look-dimensional', title: 'Dimensional surfaces', detail: 'Layered paper · precise lighting', scene: DimensionalLook },
] as const
</script>

<template>
  <div class="lk-pair">
    <figure v-for="[look, title, detail] in looks" :key="look" :class="look">
      <Stage specimen :width="358" :height="360" :compact="{ below: 358, width: 288, height: 360 }" :initial="{}">
        <Window url="app.northwind.co" class="lk-window">
          <div class="lk-body">
            <div class="lk-intro">
              <div class="lk-head">
                <Text class="lk-title">Invite your team</Text>
                <Badge tone="accent">3 seats</Badge>
              </div>
              <Text class="lk-description">Choose who can access this workspace.</Text>
            </div>
            <Field label="Email address" value="ada@northwind.co" />
            <Segmented :items="['Member', 'Admin', 'Guest']" :value="0" />
            <div class="lk-invite">
              Send invitation
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                <path
                  d="M2.5 7h9M7.5 3l4 4-4 4"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </div>
          </div>
        </Window>
      </Stage>
      <figcaption>
        <strong>{{ title }}</strong>
        <span>{{ detail }}</span>
      </figcaption>
    </figure>

    <figure v-for="{ look, title, detail, scene: Study } in studies" :key="look" :class="look">
      <Stage
        :width="358"
        :height="360"
        :compact="{ below: 358, width: 288, height: 360 }"
        greys="cool"
        :theme="look === 'look-console' ? 'dark' : 'light'"
      >
        <component :is="Study" />
      </Stage>
      <figcaption>
        <strong>{{ title }}</strong>
        <span>{{ detail }}</span>
      </figcaption>
    </figure>
  </div>
</template>
