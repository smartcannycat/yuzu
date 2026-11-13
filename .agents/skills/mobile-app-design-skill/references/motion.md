# Universal Mobile Motion Laws

Motion quality is judged in the first 10 seconds of using an app. Natural motion follows physical laws of momentum, mass, and direct manipulation.

---

## 1. The Two Families of Motion

| Family | Driver | Timing / Curve | Examples |
|---|---|---|---|
| **Responsive** (touch gesture active) | Gesture position & finger release velocity | Physics Spring (critically damped or slight settle) | Sheet drag, swipe-to-dismiss, pull-to-refresh, card pan |
| **Narrative** (system initiated) | Clock / State transition | Fast Ease-Out (under 300 ms) | Screen entrances, toasts, modal reveals, badge pop |

> [!IMPORTANT]
> Mixing them up is the #1 tell of non-native motion: a sheet that closes on a fixed 300 ms linear timing after an aggressive fling feels broken and robotic; a button that wobbles for 800 ms on tap feels sluggish.

---

## 2. Spring Physics Parameters

When a finger releases an element, motion must inherit the **release velocity** and settle smoothly:

- **Critically Damped (Snapping / Standard):** `dampingRatio: 1.0`, perceptual duration ~350–400 ms. Zero bounce, fast settle. Use for drawers, tabs, and snap points.
- **Subtle Bounce (Interactive / Playful):** `dampingRatio: 0.82`, perceptual duration ~300 ms. Single slight overshoot. Use for milestone completions, badge reveals, and toggle clicks.
- **CSS / Web Spring Equivalents:**
  ```css
  /* Crisp iOS-like ease-out for web-mobile */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-smooth: cubic-bezier(0.65, 0, 0.35, 1);
  --transition-fast: 200ms var(--ease-out-expo);
  --transition-normal: 320ms var(--ease-out-expo);
  ```

---

## 3. Press Feedback Rules

Every interactive element (button, card, list row) must acknowledge touch immediately:

1. **Press-in timing:** Feedback triggers within 100 ms of touch-down.
2. **Buttons & Cards:** Scale down subtly to `0.97` or `0.98`. Never scale below 0.95 (feels like deflating).
3. **List Rows:** Background highlight/tint (e.g. 5% black in light mode, 8% white in dark mode). Never scale whole rows.
4. **Navigation Bar Icons:** Opacity dip to `0.6` on press.
5. **Release:** Spring immediately back to `scale: 1.0` within 150 ms.

---

## 4. Performance & Reduced Motion

- **Property Restriction:** Animate ONLY `transform` (translate, scale, rotate) and `opacity`. Never animate `width`, `height`, `top`, `margin`, or `padding` (causes layout reflows and frame drops).
- **Reduced Motion Support:** Always respect system preferences:
  ```css
  @media (prefers-reduced-motion: reduce) {
    * {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
  ```
- **Frame Budget:** 60 fps (16.6 ms per frame) or 120 fps ProMotion (8.3 ms per frame). Measure on real hardware, not desktop emulators.
