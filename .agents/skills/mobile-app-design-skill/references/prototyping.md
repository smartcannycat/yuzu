# Interactive Prototyping Playbook

A key superpower of `design-mcp` is exporting real screens and user journey flows directly to disk to create clickable, interactive mobile HTML prototypes.

---

## 1. Exporting Flows from `design-mcp`

Use the `export_flow` tool to dump an ordered flow with sequential filenames and hotspot zones:

```json
{
  "flow_id": "target_flow_id",
  "out_dir": "research/prototypes/onboarding",
  "detail": "full"
}
```

The tool writes:
- `step_01_<screen_id>.jpg`
- `step_02_<screen_id>.jpg`
- ...
- A metadata summary containing the ordered steps and interactive hotspot bounding boxes `{ x, y, width, height, target_step }`.

---

## 2. Generating a Clickable Mobile Web Frame

To test and present the flow, generate a standalone `index.html` inside the export directory:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mobile Flow Prototype</title>
  <style>
    :root {
      --phone-w: 390px;
      --phone-h: 844px;
      --phone-radius: 48px;
    }
    body {
      margin: 0;
      background: #09090B;
      color: #FAFAFA;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }
    .device-shell {
      position: relative;
      width: var(--phone-w);
      height: var(--phone-h);
      border-radius: var(--phone-radius);
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 0 12px #27272A;
      overflow: hidden;
      background: #000;
    }
    .screen-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      user-select: none;
    }
    .hotspot {
      position: absolute;
      cursor: pointer;
      background: rgba(255, 255, 255, 0.0);
      transition: background 0.15s ease;
    }
    .hotspot:hover {
      background: rgba(255, 255, 255, 0.15);
    }
    .controls {
      margin-top: 24px;
      display: flex;
      gap: 12px;
      align-items: center;
    }
    button {
      background: #27272A;
      color: #FAFAFA;
      border: 1px solid #3F3F46;
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 500;
    }
    button:hover { background: #3F3F46; }
  </style>
</head>
<body>
  <div class="device-shell" id="phone">
    <img id="active-screen" class="screen-img" src="" alt="Screen">
    <div id="hotspots-container"></div>
  </div>

  <div class="controls">
    <button onclick="prevStep()">← Previous</button>
    <span id="step-indicator">Step 1 of N</span>
    <button onclick="nextStep()">Next →</button>
  </div>

  <script>
    // Injected flow steps and hotspots from export_flow output
    const flowSteps = [
      /* [{ src: 'step_01_...', hotspots: [{ x, y, w, h, target: 1 }] }] */
    ];
    let currentStep = 0;

    function renderStep(index) {
      currentStep = index;
      const step = flowSteps[currentStep];
      document.getElementById('active-screen').src = step.src;
      document.getElementById('step-indicator').textContent = `Step ${currentStep + 1} of ${flowSteps.length}`;
      
      const container = document.getElementById('hotspots-container');
      container.innerHTML = '';
      (step.hotspots || []).forEach(h => {
        const div = document.createElement('div');
        div.className = 'hotspot';
        div.style.left = h.x + '%';
        div.style.top = h.y + '%';
        div.style.width = h.w + '%';
        div.style.height = h.h + '%';
        div.onclick = () => renderStep(h.target);
        container.appendChild(div);
      });
    }

    function prevStep() { if (currentStep > 0) renderStep(currentStep - 1); }
    function nextStep() { if (currentStep < flowSteps.length - 1) renderStep(currentStep + 1); }

    renderStep(0);
  </script>
</body>
</html>
```

---

## 3. UX Validation Loop

Use the prototype to evaluate:
1. **Journey Friction:** How many taps does it take to reach the core value?
2. **Back Path Integrity:** Does clicking back from a step return the user to the expected prior state?
3. **Information Density:** Can the user scan each screen in under 3 seconds without cognitive overload?
