<script setup lang="ts">
import { Avatar, Bar, Facepile, Stage, Text, Window } from '../../kit'
import './bento.css'

// The bar for a dark, grayscale still: a bento card (360 × 280) for a music
// app, in a dark section of the page. Feature: shared playlists.
//
// Why it works: "shared" is said once, by one link. One row carries Mara's
// badge and the satellite explains it; nothing else repeats the idea. The rows
// keep album art, the thing that makes it a music app. The header is compact
// (cover beside title), so the list has room. Depth on dark comes from a
// lighter raised surface, not shadow.
//
// Story: a playlist that more than one person fills. The window shows the
// playlist with its listeners stacked beside the title; one row is new, and a
// satellite over the sidebar names who added it. Real strings: the playlist
// title and "Added by Mara". Everything else is a line or a shape.

const TRACKS = [
  { title: 62, artist: 40, art: 1 },
  { title: 48, artist: 54, art: 2 },
  { added: true, art: 3 },
  { title: 70, artist: 36, art: 4 },
  { title: 56, artist: 46, art: 5 },
]
</script>

<template>
  <Stage :width="360" :height="280" :compact="{ below: 360, width: 358, height: 280 }" theme="dark" palette="mono" class="db-card">
    <Window class="db-window" lights="grey">
      <aside class="db-sidebar">
        <div v-for="(w, i) in [46, 52, 40]" :key="i" class="db-nav">
          <Bar :w="10" :h="10" :r="3" :tone="i === 2 ? 4 : 2" />
          <Bar :w="w" :h="5" :tone="i === 2 ? 4 : 2" />
        </div>
      </aside>

      <div class="db-main">
        <header class="db-header">
          <span class="db-art db-art--cover" />
          <div class="db-heading">
            <Text class="db-title">Sunday Slow</Text>
            <div class="db-people">
              <!-- Cut out, not ringed: the gap shows the window behind -->
              <Facepile :names="['', '', '', '']" :tones="['ink', 'ink', 'ink', 'ink']" :size="18" :overlap="4" class="db-pile" />
            </div>
          </div>
        </header>

        <div class="db-list">
          <template v-for="(t, i) in TRACKS" :key="i">
            <div v-if="t.added" class="db-row" data-new>
              <span class="db-row-art">
                <span :class="`db-art db-art--${t.art} db-art--row`" />
                <Avatar name="Mara" :size="14" class="db-face db-face--row" :style="{ color: '#111113' }" />
              </span>
              <div class="db-lines">
                <Bar :w="58" :h="5" :tone="5" />
                <Bar :w="38" :h="4" :tone="3" />
              </div>
            </div>
            <div v-else class="db-row">
              <span :class="`db-art db-art--${t.art} db-art--row`" />
              <div class="db-lines">
                <Bar :w="t.title!" :h="5" :tone="3" />
                <Bar :w="t.artist!" :h="4" :tone="2" />
              </div>
            </div>
          </template>
        </div>
      </div>
    </Window>

    <!-- Satellite: the song Mara just added, over the sidebar -->
    <div class="db-detail">
      <div class="db-detail-track">
        <span class="db-art db-art--3 db-art--detail" />
        <div class="db-lines">
          <Bar :w="58" :h="5" :tone="5" />
          <Bar :w="38" :h="4" :tone="3" />
        </div>
      </div>
      <div class="db-detail-by">
        <Avatar name="Mara" :size="20" class="db-face db-face--detail" :style="{ color: '#111113' }" />
        <Text class="db-by">Added by Mara</Text>
      </div>
    </div>
  </Stage>
</template>
