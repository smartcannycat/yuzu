# MCP Playbooks: design-mcp Reference Guide

The local `design-mcp` gives you direct access to thousands of real, shipping, top-ranked mobile app screens, flows, and UI elements across iOS and Android. Use it to study real designs before writing any UI.

---

## 1. Tool Map & Signatures

| Tool | Parameters | What it returns | Typical Use |
|---|---|---|---|
| `search_screens` | `query`, `category`, `app`, `platform`, `era`, `include_images`, `limit`, `offset` | Screen metadata, titles, descriptions, OCR text, and screen URIs | Initial research: keyword & category search across real apps |
| `find_similar` | `id`, `limit` (default 8, max 30) | Screens ranked by CLIP visual embedding cosine similarity | Expanding reference pool: discover how other apps solve the same visual pattern |
| `get_screen` | `id`, `detail` (`full`, `thumb`, `data_url`, `meta`) | Single screen image (ImageContent or base64 data_url) + full metadata | Deep-dive inspection of a specific screen |
| `get_screens` | `ids` (max 20), `detail` (`full`, `thumb`, `data_url`, `meta`) | Batch retrieval of multiple screens and images in one turn | Comparative study of 5–15 benchmark screens side-by-side |
| `list_flows` | `query`, `app`, `category`, `limit`, `offset` | User journey flows matching app, category, or step names | Discovering end-to-end flows (onboarding, checkout, paywall) |
| `get_flow` | `flow_id`, `include_images`, `detail` (`thumb`, `full`, `data_url`) | Ordered steps + breadcrumbs + hotspot zones + screen images | Understanding navigation steps, modal vs push transitions, tap targets |
| `export_flow` | `flow_id`, `out_dir`, `detail` (`full` / `thumb`) | Writes sequential images (`step_01_id.jpg`) and hotspot coordinates to disk | Instant interactive HTML prototyping and offline reference |
| `export_screens` | `ids`, `out_dir`, `detail` (`full` / `thumb`) | Writes screen images directly to local directory | Creating local asset boards, design presentations, or mockups |
| `list_categories` | None | All 43 taxonomy v1 categories (e.g. `paywall-subscription`, `onboarding`, `checkout`) | Exploring standardized taxonomy to find relevant category tags |
| `list_apps` | None | List of unique mobile apps indexed in database | Checking available reference apps for competitive analysis |

---

## 2. The 3-Stage Research Pipeline

### Stage 1: Broad Search & Category Discovery
Start by finding screens in the relevant category or with matching text/OCR:
```json
// Example: Search paywalls on iOS with thumbnail images
{
  "category": "paywall-subscription",
  "platform": "ios",
  "era": "modern",
  "include_images": true,
  "limit": 10
}
```
Or search by intent via FTS/OCR:
```json
// Example: Search habit tracker progress or streak screens
{
  "query": "streak progress habit",
  "platform": "ios",
  "include_images": true,
  "limit": 10
}
```

### Stage 2: Visual Expansion via CLIP (`find_similar`)
When you locate a screen that has an exceptionally strong layout, card hierarchy, or visual structure:
```json
// Example: Find visually similar screens across the entire library
{
  "id": "screen_id_from_stage_1",
  "limit": 8
}
```
Fetch the similar screens in batch via `get_screens(ids=[...], detail="thumb")` to see alternative solutions to the same design problem across different industries.

### Stage 3: Flow & Hotspot Analysis (`get_flow` / `export_flow`)
To understand full multi-step journeys (onboarding questionnaires, checkout funnels, multi-step settings):
```json
// Example: Get complete ordered flow with hotspot tap zones
{
  "flow_id": "flow_id_found_in_list_flows_or_search",
  "include_images": true,
  "detail": "thumb"
}
```
Examine:
- Where the primary CTA sits across steps (floating bottom, sticky bottom, inline).
- How one-way doors are presented (when Back is allowed vs when Close dismisses).
- How progress is communicated (segmented bar, dots, percentage, step counter).

---

## 3. Exporting for Interactive Prototyping

Use `export_flow` to save screens and interactive hotspots to disk:
```json
{
  "flow_id": "target_flow_id",
  "out_dir": "research/prototypes/onboarding",
  "detail": "full"
}
```
This exports:
- `step_01_<id>.jpg`, `step_02_<id>.jpg` ... in journey order.
- Hotspot bounding boxes `{ x, y, width, height, target_step }` ready to be wired into a lightweight HTML/CSS mobile prototype frame.
