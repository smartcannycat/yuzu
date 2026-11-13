# Mobile Performance & Perceived Speed

Smooth 60 fps / 120 fps perceived performance is a design feature. Jitter, layout shifts, and slow response times break immersion immediately.

---

## 1. Perceived Performance Rules

1. **Optimistic Updates:** Taps and toggles update UI state instantly (<16 ms). Network requests resolve in the background and roll back with notification only on failure.
2. **Skeleton Screens vs Spinners:** Use skeleton placeholders only for structured layouts with predictable shapes (cards, profile feeds). Use progressive loading or inline indicators for dynamic content. Never show a full-screen spinner for a partial update.
3. **Preload on Touch-Down:** Trigger asset fetching and data prefetching on `touchstart` / `pointerdown`, not after `click` / navigation complete. This gains 100–250 ms of head start.
4. **List Virtualization:** Any list exceeding 15 items must be virtualized (FlashList for React Native, virtual scrolling for web). Provide stable, unique keys.

---

## 2. Web-Mobile Performance Essentials

- **Layout Stability (CLS = 0):** Reserve explicit width/height or aspect-ratio on all images and video containers before loading to prevent layout jumps.
- **Font Display:** Use `font-display: swap` with matched fallback font metrics (`size-adjust`, `ascent-override`) to avoid FOIT (Flash of Invisible Text).
- **CSS Containment:** Use `contain: content` or `content-visibility: auto` on offscreen sections in long scrolling feeds to minimize main thread render work.
- **Image Optimization:** Serve modern formats (`webp`, `avif`) with responsive `srcset` tailored to `@2x` / `@3x` mobile DPIs.
