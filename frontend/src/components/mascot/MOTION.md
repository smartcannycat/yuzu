# MOTION.md: living illustrations in YUZU

## Part 1. The method

**The goal:** anything drawn (a character, a prop, an auction sheet, a flag, a signal light) feels alive and calm. Nothing teleports, nothing bounces, nothing shouts.

### Principles

1. **Never teleport:** interpolate everything; never swap disconnected drawings.
2. **Calm by default:** strong curves, no bouncy overshoot.
3. **Small amplitudes:** when unsure, halve it.
4. **Arcs and pivots:** each moving part is a layer rotating around its joint (neck pivot, ear base, flag pole grip, loupe handle).
5. **Overlap and follow-through:** tips and trailing parts move later and further; give each part the same wave with a growing phase delay (`90-140 ms`).
6. **Variety without chaos:**
   - repeated items (`Zzz`, floating question marks) get a seeded phase, speed, and size;
   - nothing moves in sync, and there is no random value per frame.
7. **One main action per scene, plus two or three idle loops.** Side elements stay quiet.
8. **Opacity only to appear or disappear.**
9. **The layout never moves:** motion lives inside the SVG drawing (`viewBox="0 0 200 170"`).
10. **Reduced motion:** loops freeze on frame 0, and state changes apply instantly.
11. **Nothing runs unseen:** pause off screen (`IntersectionObserver`), when hidden (`visibilitychange`), and in the background.
12. **Enough frames:** blinks close in ~110 ms and reopen in ~190 ms with `out` easing.

---

## Part 2. YUZU CapyMascot Rig ("Zen Inspector")

### Where the code lives

- **Platform:** Web, Vue 3 (`<script setup lang="ts">`), inline SVG.
- **Motion engine & contract mapper:** `src/components/mascot/motion.ts` (`track`, `wave`, `loop`, `bell`, `seeded`, curves, `createChannels`, and `resolveCapyState`).
- **Art + rig:** `src/components/mascot/CapyMascot.vue`. `viewBox="0 0 200 170"`, floor line `y = 150`. The head is its own layer: `88` wide, center `(0, 0)`, neck pivot `(0, 30)`.
- **Clock:** a single `requestAnimationFrame` loop per mascot instance; paused off screen and when the document tab is hidden; frozen at `t = 0` under `prefers-reduced-motion: reduce`.

### Canonical States and API Contract Mapping

One continuous capybara rig morphs across 7 states (`CapyState`) without swapping separate vector files:

1. `sleeping` (Default / Dropzone idle / `MascotMood.SLEEPING`):
   - Wide sleeping loaf (`sit = 0`, `bodyW = 126`, `bodyH = 56`, `headY = 94`, `tilt = 5`).
   - Closed calm eyelids, slow volume-preserving breathing (`4200 ms`), double right-ear twitch every `5600 ms`, three drifting `Zzz` glyphs.
2. `peeking` (Dropzone file staged or drag-over active):
   - Loaf lifts slightly (`sit = 0.18`, `headY = 89`), `Zzz` fade out, ears perk up (`ear = 2`), eyes open (`eyeOpen = 0.85`) and look down toward the staged auction sheets (`lookY = 3`).
3. `thinking` (Screen 3 Live Polling / `BatchStatus.PROCESSING` / `MascotMood.THINKING`):
   - Capybara sits upright (`sit = 1`, `headY = 74`), inspecting a floating auction sheet card in front of her.
   - An orange scan beam (`#FF6B00`) sweeps vertically across the sheet while the right paw holds an inspector's magnifying glass (`loupe`) gliding in a 6.4s 2-phase inspection loop (reading lines -> squinting through the loupe).
4. `green` (Screen 4 Safe Verdict / `TrafficLightColor.GREEN` / `MascotMood.HAPPY`):
   - Cheerful upward-arch closed eyes (`happy = 1`), lifted rosy cheeks, warm smile.
   - Right paw holds an angled pole with a green checkmark flag (`#58CC02` / `#58A700`) topped by the signature golden **Yuzu citrus finial** (`#FFC800` / `#FFB100` with a green leaf) that waves on entrance and rocks with follow-through.
5. `yellow` (Screen 4 Caution Verdict / `TrafficLightColor.YELLOW` / `BatchStatus.PARTIAL_FAILED` / `MascotMood.CONFUSED`):
   - Skeptical head tilt (`tilt = -5`), asymmetric expert squint (`lidRightExtra = 0.44`), left paw raised to chin (`pawLX = 86, pawLY = 110`).
   - Right paw holds a rounded yellow caution sign (`#FFC800` / `#FFB100`) with a dark exclamation mark (`!`).
6. `red` (Screen 4 Stop-Factor Verdict / `TrafficLightColor.RED` / `MascotMood.WARNING`):
   - Stern horizontal upper eyelids (`lidFlat = 0.36`), inverted frown mouth (`frown = 1`), and an entrance head-shake ("no") over `850 ms`.
   - Right paw holds a dark traffic light housing (`#3C3C3C`) with an active top red lamp (`#FF4B4B`) and pulsing red warning arcs.
7. `error` (Gatekeeper Reject / OCR Failure / `BatchStatus.FAILED` / `ItemProcessingStatus.FAILED`):
   - Sympathetic shrug pose (`shrug = 1`): both paws raised and spread outward (`pawLX = 48, pawLY = 116`, `pawRX = 152, pawRY = 113`), head tilted (`tilt = -8`), drooped ears (`ear = 20`), sloped worried upper lids (`sadTilt = 1`), and drifting question marks (`?`).

### Display Modes (No-Clown Policy)

- `size="hero"` (Screen 2 Dropzone, Screen 3 Processing Queue, Empty/Error states):
  - `208 x 176 px` stage (`w-52 h-44`) with an optional status pill below.
- `size="compact"` (Screen 4 Verdict Cards, `80 x 80 px` avatar container):
  - `hideBadge = true`. Plays the full state transition and a `1200 ms` arrival accent (flag wave, caution bob, or red head-shake), then settles into a calm, low-amplitude breathing and 4s blink loop so financial metrics remain the primary focus.
