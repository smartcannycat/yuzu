# Universal Control Selection & Platform Mapping

Benchmark-quality mobile apps respect user muscle memory by adhering to platform control conventions. Use this matrix to map user needs to native behaviors across iOS, Android, and Web-Mobile.

---

## 1. Cross-Platform Control Matrix

| Need | iOS (Apple HIG) | Android (Material Design 3) | Web-Mobile (Touch Standards) |
|---|---|---|---|
| **Toggle state** | `UISwitch` (pill, smooth 51x31pt slide) | `Switch` (Material 3 with check icon inside thumb) | Accessible toggle (`role="switch"`, 48x28px, min 44px hit-box) |
| **Segmented Choice (2–5 items)** | `UISegmentedControl` (sliding pill over rounded container) | `SegmentedButtons` (outlined connected containers) | Segmented bar (`flex: 1`, active pill with spring animation) |
| **Contextual Menu** | `UIMenu` / Context Menu (haptic on long-press, blurred backdrop) | Popup Menu / Bottom Sheet | Long-press or 3-dots touch trigger to modal bottom sheet |
| **Destructive Confirmation** | `ActionSheet` (bottom-anchored red text options) | Modal Dialog / Bottom Sheet with error button | Bottom-sheet dialog with prominent red action and Cancel |
| **Temporary Sheet / Filter** | `UISheetPresentationController` (detents: medium/large) | Modal Bottom Sheet with drag handle | Drag-to-dismiss bottom sheet with `overscroll-behavior: contain` |
| **Date & Time Picker** | Inline calendar or wheel spinner | Material Date Picker modal / docked | Native `<input type="date">` / `<input type="time">` to invoke OS picker |
| **Single Select from long list** | Push to selection list or wheel picker | Dropdown menu or full dialog | Native `<select>` or custom searchable bottom sheet |
| **Search Input** | Navigation bar integrated search (`UISearchController`) | Top search bar (`SearchBar` / `SearchView`) | Sticky header search with clear button (`type="search"`) |
| **Pull to Refresh** | `UIRefreshControl` (iOS spinner at top) | `SwipeRefreshLayout` (circular Material spinner) | Native pull-to-refresh or touch-drag indicator |
| **Primary Page Action** | Top-right navigation bar button or sticky bottom CTA | Floating Action Button (FAB) or bottom bar | Full-width sticky bottom CTA (with `env(safe-area-inset-bottom)`) |

---

## 2. Platform Nuances & Guidelines

### iOS (Apple HIG)
- **Continuous Corners (Squircles):** Apply continuous corner curves (`borderCurve: 'continuous'`).
- **SF Symbols:** Use SF Symbols with matching font weights (Regular/Medium/Semibold) and optical sizes.
- **Haptic Punctuation:** Pair selection ticks, success notifications, and snap-to-edge moments with subtle haptics.
- **Large Titles:** Expand to Large Title at top of scroll; smoothly collapse into standard nav bar title on scroll down.

### Android (Material Design 3)
- **Edge-to-Edge:** UI draws under status bar and 3-button/gesture navigation bar; use transparent system bars.
- **Tonal Elevation:** Surfaces use tonal color shifts rather than heavy drop shadows to denote elevation.
- **Predictive Back:** Ensure pages and sheets handle the system predictive back swipe smoothly without jarring cuts.
- **Material Symbols:** Use 24dp Material Symbols (Outlined, Rounded, or Sharp consistently).

### Web-Mobile
- **Hit Areas:** Never rely on visual element bounds alone; pad all clickable targets to at least 44x44px (iOS) / 48x48px (Android).
- **Fast Touch:** Set `touch-action: manipulation` to remove 300ms tap delay.
- **Input Font Size:** Always use at least 16px font-size on inputs to stop iOS Safari auto-zooming.
- **Safe Area Insets:** Use `calc(var(--padding) + env(safe-area-inset-*))` on all fixed/sticky headers and footers.
