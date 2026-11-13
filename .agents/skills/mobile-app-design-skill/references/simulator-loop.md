# Multi-Platform Mobile Verification Loop

A screen or mobile flow does not exist until you have validated it in a live mobile viewport. Code review alone cannot detect optical misalignment, gesture conflicts, or scroll jank.

---

## 1. Platform Verification Matrix

| Target | Verification Environment | Primary Inspection Focus |
|---|---|---|
| **iOS** | iOS Simulator (`xcrun simctl`) | Dynamic Island / Notch safe areas, SF Symbols weight, large title collapse, edge swipe back |
| **Android** | Android Emulator / Physical Device | Edge-to-edge transparent system bars, 3-button/gesture nav, Material 3 dynamic color, back button |
| **Web-Mobile** | Chrome DevTools Device Mode / Safari Mobile Inspector | `100dvh` address bar expand/collapse, touch target hitboxes, safe area CSS insets, fast tap response |
| **HTML Prototype** | Browser Phone Frame (390x844 / 412x915) | Journey flow completion, hotspot tap accuracy, transition continuity |

---

## 2. The Verification Pass (Checklist per Flow)

Record or step through the flow end-to-end, testing:

1. **Light & Dark Mode:**
   - Does every surface, card, and text label resolve to high-contrast tokens in both light and dark?
   - Are borders subtle (e.g. 1px 10% white in dark mode) rather than stark?
2. **Dynamic Insets & Scrolling:**
   - Scroll content fully under the status bar / Dynamic Island. Does the blur or header scrim hold cleanly?
   - Scroll to the bottom: does the primary CTA clear the home indicator bar?
3. **Keyboard Interactions:**
   - Focus an input at the bottom of the screen. Does the view scroll smoothly to keep the input visible?
   - Dismiss the keyboard. Does layout return to rest without jump-cuts or white flashes?
4. **Edge Cases:**
   - Long localized text: Does text wrap naturally or truncate with ellipsis cleanly?
   - Empty states: Is an engaging illustration/icon paired with actionable guidance on how to populate the view?
   - Loading skeletons: Do skeleton shapes match the actual layout dimensions?
5. **Back Navigation & One-Way Doors:**
   - Does back undo navigation, not application state?
   - Behind a one-way door (after sign-in, paywall purchase, onboarding completion), verify that back CANNOT re-enter the protected state.
