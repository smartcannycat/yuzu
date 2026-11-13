# Stageshow (Vue 3 + TypeScript)

A skill and a Vue 3 kit for product illustrations, cursor stories, and
motion design. Start with `SKILL.md`; follow its links for the task at hand.

## Preview

Requires Bun (1.1+) or Node 20.19+. From this folder:

```sh
bun install
bun run dev
```

On macOS and Linux with Portless, open **http://stageshow.localhost:1355**. Otherwise,
Vite starts directly; open the local URL it prints (normally **http://127.0.0.1:5173**).

The playground includes the gold
examples, nine visual styles, and labeled bad/good teaching pairs.
Pause, replay, slow down, or advance one frame. Phone changes the available
width to 358px; Reduced motion shows each scene's still. The viewer and its
controls stay outside the example's isolated clock.

## Use the kit

Copy `kit/` into your Vue 3 project. Its components import their own CSS:

```vue
<script setup lang="ts">
import { Stage, Window, type Act } from './kit'
</script>

<template>
  <Stage :width="720" :height="420">
    <Window url="app.example.com">
      <!-- Your faux UI here -->
    </Window>
  </Stage>
</template>
```

Copy an example as a starting point. Keep its relative kit imports, copy any
assets it imports, and adapt the composition and look to your product. These
are authored illustrations: a scripted `a.click()` draws feedback; `a.set()`
changes the scene. They do not automate real application controls.

Real-product studies are included in
`examples/` and listed under **Real products** in the playground. Icons use
`lucide-vue-next`, which the playground installs. When copying a study into a
different project, keep its local assets and install that icon dependency or
adapt the icons.

The kit supports Vue 3.5+ and 100% strict TypeScript. It needs no third-party animation runtime. The
playground uses Vite 6+; filming uses `playwright-core` and locally installed
Chrome (or `CHROME_PATH`). Those tools are not runtime dependencies of a demo.

## Verify

```sh
bun run typecheck
bun run check:css
node scripts/film.mjs '<your URL>' --select '.your-demo' --gate
node scripts/film.mjs '<your URL>' --select '.your-demo' --width 390 --gate
node scripts/film.mjs '<your URL>' --select '.your-demo' --states --gate
```

For the bundled viewer, use `?capture=hero-demo` as the filming URL. The ordinary
viewer contains an iframe; use the direct capture route on native clocks. See
`references/rehearse.md` for coverage, phone, hover, reduced-motion, and visual
review. No automated clean result replaces watching the motion.

## Contents

- `kit/`: portable Vue 3 TypeScript source and styles.
- `examples/`: gold scenes and reference specimens.
- `teaching/`: explicitly flawed/corrected pairs, separate from gold.
- `references/`: design judgment, APIs, and verification guidance.
- `assets/`: local icon assets used by examples.
- `scripts/`: verification tools, independent of the host's markup.
- `playground/`: the standalone local Vue 3 viewer.

The skill, kit, examples and verification tools are included in this folder.
See `NOTICE.md` for third-party names and optional assets.
