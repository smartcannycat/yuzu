# Web-Mobile Design & Implementation Laws

Web-mobile screens run in mobile browsers (Safari iOS, Chrome Android, WebViews, PWA). Without strict mobile-first discipline, a web page feels like a clumsy desktop site crammed onto a small screen.

Follow these native-fidelity rules for all mobile web interfaces.

---

## 1. Viewport & Safe Areas

### Viewport Units: Never use `100vh` on mobile
Mobile browser address bars and toolbars expand and collapse dynamically on scroll.
- **`100dvh` (Dynamic Viewport Height):** Adapts continuously as address bars show/hide. Use for full-height screens, modal drawers, and sticky headers/footers.
- **`100svh` (Small Viewport Height):** Height when browser chrome is fully expanded. Ideal for initial screen fold calculations (prevents bottom CTAs from being covered on first render).
- **`100lvh` (Large Viewport Height):** Height when browser chrome is completely hidden.

```css
/* Full screen container */
.mobile-screen {
  min-height: 100vh; /* fallback */
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}
```

### Safe Area Insets (`env(safe-area-inset-*)`)
To clear the iPhone notch, Dynamic Island, and home indicator bar:
1. Always set `<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">`.
2. Apply padding using CSS environment variables:

```css
:root {
  --sat: env(safe-area-inset-top, 0px);
  --sar: env(safe-area-inset-right, 0px);
  --sab: env(safe-area-inset-bottom, 0px);
  --sal: env(safe-area-inset-left, 0px);
}

.header {
  padding-top: calc(12px + var(--sat));
}

.sticky-bottom-cta {
  padding-bottom: calc(16px + var(--sab));
}
```

---

## 2. Touch Targets & Input Discipline

### Sizing Rules
- **Minimum Tap Target:** 44x44 px (Apple HIG) / 48x48 px (Android Material). Even if the visible icon is 20px, the clickable hit-area must be padded to at least 44–48px.
- **Spacing between clickable elements:** Minimum 8px to prevent accidental adjacent taps.

### Mobile Input Zoom Prevention
In iOS Safari, focusing any input with a font size smaller than `16px` triggers an automatic, jarring viewport zoom.
- **Always set `font-size: 16px` (or 1rem with 16px root)** on all `<input>`, `<textarea>`, and `<select>` elements.

```css
input, select, textarea {
  font-size: 16px; /* Prevents auto-zoom in iOS Safari */
}
```

---

## 3. Gestures, Scroll, and Anti-Slop CSS

Eliminate standard web browser behaviors that give away that a mobile interface is a web page:

```css
/* Mobile baseline styles */
html, body {
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  /* Prevent horizontal wobble */
  overflow-x: hidden;
  /* Prevent pull-to-refresh & rubber-band conflicts on body */
  overscroll-behavior-y: contain;
}

/* Fast tap response (removes 300ms tap delay without breaking pinch-to-zoom) */
button, a, [role="button"], input, select {
  touch-action: manipulation;
  /* Remove gray/blue tap highlight box */
  -webkit-tap-highlight-color: transparent;
}

/* Prevent text selection and magnifying callouts on UI controls */
.interactive-control {
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

/* Smooth momentum scrolling for internal scroll areas */
.scroll-container {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
```

---

## 4. Navigation & Bottom Sheets in Web-Mobile

1. **Back Navigation:** Web-mobile must respect browser History API (`history.pushState` vs `history.replaceState`).
   - Tapping Back on Android browser or swiping from edge on iOS Safari must dismiss open modals, drawers, and search states first before leaving the page.
2. **Bottom Sheets:** Use native drag gestures with spring curves. Limit sheet height to `calc(90dvh - var(--sat))` so it never covers the status bar completely.
3. **PWA Standalone & Theme Color:**
   ```html
   <meta name="apple-mobile-web-app-capable" content="yes">
   <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
   <meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
   <meta name="theme-color" content="#09090B" media="(prefers-color-scheme: dark)">
   ```
