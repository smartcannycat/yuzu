<script setup lang="ts">
import {
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  Clock3,
  House,
  Library,
  ListMusic,
  MicVocal,
  MonitorSpeaker,
  Pause,
  Plus,
  Repeat,
  Search,
  Shuffle,
  SkipBack,
  SkipForward,
  Volume2,
} from 'lucide-vue-next'
import { Bar, Stage, Swap, Text, Window, type Act } from '../../kit'
import './spotify.css'

// Spotify desktop, dark, about 860 wide. A hero loop.
//
// Story: a playlist is open and "Low Tide" is playing from it (green title,
// equaliser in place of its number). The cursor double-clicks "Neon Harbor"
// two rows down: the green and the equaliser move to that row, the
// now-playing bar swaps art, title and artist, the total time changes and
// the progress bar starts again from 0:00 and keeps moving. After a hold the
// cursor double-clicks "Low Tide" again, which restarts it from 0:00: the
// exact frame the loop opens on, so the reset is caused, not a seam.
//
// Real strings: the playlist title, the two songs and their artists, the two
// times. Everything else is a line or album art.
// Icons: Spotify's own set isn't available, so lucide, chosen for its plain
// geometric strokes, which are close to Spotify's; play and pause are filled.

type Id = 'a' | 'b'
type S = { playing: Id; sel: Id; elapsed: number }

const initial: S = { playing: 'a', sel: 'a', elapsed: 0 }

const SONGS: Record<Id, { title: string; artist: string; art: number; dur: number }> = {
  a: { title: 'Low Tide', artist: 'Marlo', art: 2, dur: 196 },
  b: { title: 'Neon Harbor', artist: 'The Vales', art: 4, dur: 168 },
}

// Rows of the playlist. Real text only on the two songs the story plays.
const ROWS: { id?: Id; art: number; t: number; ar: number; al: number }[] = [
  { id: 'a', art: 2, t: 0, ar: 0, al: 58 },
  { art: 3, t: 52, ar: 46, al: 82 },
  { id: 'b', art: 4, t: 0, ar: 0, al: 64 },
  { art: 1, t: 64, ar: 40, al: 70 },
  { art: 5, t: 70, ar: 34, al: 50 },
  { art: 6, t: 58, ar: 44, al: 74 },
]

const LIB_ROWS: { art: number; t: number; m: number; on?: boolean }[] = [
  { art: 7, t: 72, m: 50, on: true },
  { art: 3, t: 54, m: 62 },
  { art: 8, t: 66, m: 40 },
  { art: 5, t: 48, m: 56 },
  { art: 1, t: 60, m: 44 },
  { art: 6, t: 52, m: 58 },
  { art: 2, t: 68, m: 42 },
]

const IDS: Id[] = ['a', 'b']

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

async function script(a: Act<S>) {
  // The song keeps playing under everything the cursor does
  let live = true
  ;(async () => {
    try {
      while (live) {
        await a.wait(1000)
        if (live) a.put((s) => ({ elapsed: s.elapsed + 1 }))
      }
    } catch {
      /* stopped */
    }
  })()

  await a.wait(1400)

  // Play Neon Harbor
  a.mark('play')
  await a.move({ at: 'row-b', x: 0.72, y: 0.5 })
  await a.wait(350)
  await a.click(undefined, { double: true })
  await a.set({ playing: 'b', sel: 'b', elapsed: 0 })
  await a.wait(1100)

  // Down to the player, where the new song is running: hovering the
  // progress bar lights it green and shows its handle, as Spotify does
  a.mark('progress')
  await a.move({ at: 'progress', x: 0.62, y: 0.5 })
  await a.wait(4400)

  // Back to Low Tide, which starts again from the top: the opening frame
  a.mark('back')
  await a.move({ at: 'row-a', x: 0.72, y: 0.5 })
  await a.wait(350)
  await a.click(undefined, { double: true })
  live = false
  await a.set({ playing: 'a', sel: 'a', elapsed: 0 })
}
</script>

<template>
  <Stage
    :width="860"
    :height="600"
    :compact="{ below: 600, width: 400, height: 520 }"
    :initial="initial"
    :script="script"
    theme="dark"
    accent="#1ed760"
    :cursor="{ at: { at: 'row-a', x: 0.72, y: 0.5 } }"
    class="spt-stage"
    v-slot="{ state: s, layout }"
  >
    <Window class="spt-window" :data-layout="layout">
      <template #lead>
        <span class="spt-nav">
          <ChevronLeft :size="18" :stroke-width="2" />
          <ChevronRight :size="18" :stroke-width="2" class="spt-faint" />
        </span>
        <span class="spt-center">
          <span class="spt-home">
            <House :size="16" :stroke-width="2" />
          </span>
          <span class="spt-search">
            <Search :size="15" :stroke-width="2" />
            <Bar :w="layout === 'compact' ? 96 : 196" :h="5" :tone="3" />
          </span>
        </span>
      </template>

      <template #toolbar>
        <span class="spt-me" />
      </template>

      <div class="spt-panels">
        <!-- Your Library -->
        <aside class="spt-library" data-crop>
          <div v-if="layout === 'compact'" class="spt-lib-head spt-lib-head--rail">
            <Library :size="18" :stroke-width="2" />
          </div>
          <template v-else>
            <div class="spt-lib-head">
              <Library :size="18" :stroke-width="2" />
              <Text class="spt-lib-title">Your Library</Text>
              <span class="spt-spacer" />
              <Plus :size="16" :stroke-width="2" />
            </div>
            <div class="spt-chips">
              <Bar :w="58" :h="24" :r="12" :tone="2" />
              <Bar :w="48" :h="24" :r="12" :tone="2" />
            </div>
          </template>
          <div class="spt-lib-list" data-crop>
            <div v-for="(p, i) in LIB_ROWS" :key="i" class="spt-lib-row" :data-on="p.on || undefined">
              <span :class="`spt-art spt-art--${p.art} spt-art--lib`" />
              <span v-if="layout !== 'compact'" class="spt-lines">
                <Bar :w="p.t" :h="5" :tone="p.on ? 5 : 3" />
                <Bar :w="p.m" :h="4" :tone="2" />
              </span>
            </div>
          </div>
        </aside>

        <!-- The playlist -->
        <main class="spt-main" data-crop>
          <header class="spt-header">
            <span class="spt-art spt-art--7 spt-art--cover" />
            <div class="spt-heading">
              <Bar :w="44" :h="4" :tone="4" />
              <Text class="spt-title">Late Night Drive</Text>
              <span class="spt-meta">
                <span class="spt-meta-dot" />
                <Bar :w="layout === 'compact' ? 60 : 96" :h="4" :tone="3" />
              </span>
            </div>
          </header>

          <div class="spt-actions">
            <span class="spt-bigplay">
              <Pause :size="18" :stroke-width="0" fill="currentColor" />
            </span>
            <Shuffle :size="20" :stroke-width="2" class="spt-faint-icon" />
            <CirclePlus :size="20" :stroke-width="2" class="spt-faint-icon" />
            <span class="spt-more">
              <i />
              <i />
              <i />
            </span>
          </div>

          <div class="spt-tracks">
            <div class="spt-row spt-row--head">
              <span class="spt-num">#</span>
              <Bar :w="30" :h="4" :tone="3" />
              <Bar v-if="layout !== 'compact'" :w="34" :h="4" :tone="3" />
              <Clock3 :size="14" :stroke-width="2" class="spt-faint-icon spt-dur" />
            </div>
            <div
              v-for="(r, i) in ROWS"
              :key="i"
              class="spt-row"
              :data-target="r.id ? `row-${r.id}` : undefined"
              :data-playing="r.id === s.playing || undefined"
              :data-selected="r.id === s.sel || undefined"
            >
              <span class="spt-num">
                <span class="spt-num__n">{{ i + 1 }}</span>
                <span class="spt-eq" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
              </span>
              <span class="spt-song">
                <span :class="`spt-art spt-art--${r.art} spt-art--row`" />
                <span v-if="r.id" class="spt-song-text">
                  <span class="spt-song-title">{{ SONGS[r.id].title }}</span>
                  <span class="spt-song-artist">{{ SONGS[r.id].artist }}</span>
                </span>
                <span v-else class="spt-lines">
                  <Bar :w="r.t" :h="5" :tone="4" />
                  <Bar :w="r.ar" :h="4" :tone="2" />
                </span>
              </span>
              <Bar v-if="layout !== 'compact'" :w="r.al" :h="4" :tone="2" />
              <span class="spt-dur">
                <Bar :w="24" :h="4" :tone="2" />
              </span>
            </div>
          </div>
        </main>
      </div>

      <!-- Now playing -->
      <footer class="spt-player">
        <div class="spt-now">
          <span class="spt-now-art">
            <span
              v-for="id in IDS"
              :key="id"
              :class="`spt-art spt-art--${SONGS[id].art} spt-art--now${s.playing === id ? ' is-on' : ''}`"
            />
          </span>
          <span class="spt-now-text">
            <span
              v-for="id in IDS"
              :key="id"
              class="spt-now-song"
              :data-on="s.playing === id || undefined"
              :aria-hidden="s.playing !== id || undefined"
            >
              <span class="spt-now-title">{{ SONGS[id].title }}</span>
              <span class="spt-now-artist">{{ SONGS[id].artist }}</span>
            </span>
          </span>
          <CirclePlus v-if="layout !== 'compact'" :size="16" :stroke-width="2" class="spt-faint-icon" />
        </div>

        <div class="spt-transport">
          <div class="spt-controls">
            <Shuffle :size="16" :stroke-width="2" class="spt-faint-icon" />
            <SkipBack :size="16" :stroke-width="0" fill="currentColor" class="spt-ctl" />
            <span class="spt-playbtn">
              <Pause :size="14" :stroke-width="0" fill="currentColor" />
            </span>
            <SkipForward :size="16" :stroke-width="0" fill="currentColor" class="spt-ctl" />
            <Repeat :size="16" :stroke-width="2" class="spt-faint-icon" />
          </div>
          <div class="spt-progress">
            <span class="spt-t spt-t--start">{{ fmt(s.elapsed) }}</span>
            <span class="spt-track" data-target="progress">
              <span
                :key="s.playing"
                class="spt-fill"
                :style="{ clipPath: `inset(0 ${(1 - s.elapsed / SONGS[s.playing].dur) * 100}% 0 0 round 2px)` }"
              />
              <span
                :key="`k${s.playing}`"
                class="spt-knob"
                :style="{ transform: `translateX(${(s.elapsed / SONGS[s.playing].dur) * 100}%)` }"
              >
                <i />
              </span>
            </span>
            <span class="spt-t">
              <Swap :id="s.playing" :duration="500">
                {{ fmt(SONGS[s.playing].dur) }}
              </Swap>
            </span>
          </div>
        </div>

        <div class="spt-extras" :hidden="layout === 'compact'">
          <MicVocal :size="16" :stroke-width="2" class="spt-faint-icon" />
          <ListMusic :size="16" :stroke-width="2" class="spt-faint-icon" />
          <MonitorSpeaker :size="16" :stroke-width="2" class="spt-faint-icon" />
          <Volume2 :size="16" :stroke-width="2" class="spt-faint-icon" />
          <span class="spt-volume">
            <span />
          </span>
        </div>
      </footer>
    </Window>
  </Stage>
</template>
