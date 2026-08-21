(function () {
  const dataEl = document.getElementById("dashboard-data");
  if (!dataEl) return;
  const initial = JSON.parse(dataEl.textContent);

  const RING_COLORS = {
    transport: "#8a5a3b",
    electricity: "#dba53d",
    lpg: "#bf5340",
    food: "#3f6a4f",
    waste: "#8fb08f",
  };
  const RING_LABELS = {
    transport: "Transport",
    electricity: "Electricity",
    lpg: "LPG",
    food: "Food & diet",
    waste: "Waste",
  };

  // ---------------- Loading / tips sequence ----------------
  const loadingScreen = document.getElementById("loading-screen");
  const loadingTip = document.getElementById("loading-tip");
  const contentSections = [
    document.getElementById("dashboard-content"),
    document.getElementById("breakdown-section"),
    document.getElementById("whatif-section"),
  ];

  let tipIndex = 0;
  const tips = initial.tips && initial.tips.length ? initial.tips : ["Small changes add up."];
  const tipTimer = setInterval(() => {
    tipIndex = (tipIndex + 1) % tips.length;
    loadingTip.textContent = tips[tipIndex];
  }, 900);

  setTimeout(() => {
    clearInterval(tipTimer);
    loadingScreen.hidden = true;
    contentSections.forEach((s) => s && (s.hidden = false));
    renderRingGauge(initial.result, initial.contributors);
    renderContributors(initial.contributors);
  }, 1800);

  // ---------------- Growth-ring gauge ----------------
  function renderRingGauge(result, contributors) {
    const svg = document.getElementById("ring-gauge");
    if (!svg) return;
    svg.innerHTML = "";
    const ns = "http://www.w3.org/2000/svg";
    const cx = 120, cy = 120;
    const startRadius = 30, step = 17;

    contributors.forEach((c, i) => {
      const r = startRadius + i * step;
      const circumference = 2 * Math.PI * r;
      const share = Math.max(0, Math.min(100, c.share)) / 100;

      const track = document.createElementNS(ns, "circle");
      track.setAttribute("cx", cx);
      track.setAttribute("cy", cy);
      track.setAttribute("r", r);
      track.setAttribute("fill", "none");
      track.setAttribute("stroke", "rgba(22,36,28,0.08)");
      track.setAttribute("stroke-width", 10);
      svg.appendChild(track);

      const arc = document.createElementNS(ns, "circle");
      arc.setAttribute("cx", cx);
      arc.setAttribute("cy", cy);
      arc.setAttribute("r", r);
      arc.setAttribute("fill", "none");
      arc.setAttribute("stroke", RING_COLORS[c.category] || "#3f6a4f");
      arc.setAttribute("stroke-width", 10);
      arc.setAttribute("stroke-linecap", "round");
      arc.setAttribute("stroke-dasharray", `${circumference * share} ${circumference}`);
      arc.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
      arc.style.transition = "stroke-dasharray 0.5s ease";
      svg.appendChild(arc);
    });

    document.getElementById("gross-figure").textContent = result.gross;
    document.getElementById("offset-figure").textContent = "\u2212" + result.total_offsets;
  }

  function renderContributors(contributors) {
    const wrap = document.getElementById("contributors-list");
    if (!wrap) return;
    wrap.innerHTML = "";
    contributors.forEach((c) => {
      const row = document.createElement("div");
      row.className = "contributor-row";
      row.innerHTML = `
        <span class="label" style="color:${RING_COLORS[c.category] || "#3f6a4f"}">${RING_LABELS[c.category] || c.category}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${c.share}%; background:${RING_COLORS[c.category] || "#3f6a4f"}"></span></span>
        <span class="pct">${c.share}%</span>
      `;
      wrap.appendChild(row);
    });
  }

  // ---------------- What-if simulator ----------------
  const sliders = {
    distance: document.getElementById("w-distance"),
    electricity: document.getElementById("w-electricity"),
    lpg: document.getElementById("w-lpg"),
    meat: document.getElementById("w-meat"),
    waste: document.getElementById("w-waste"),
    trees: document.getElementById("w-trees"),
  };
  const labels = {
    distance: document.getElementById("v-distance"),
    electricity: document.getElementById("v-electricity"),
    lpg: document.getElementById("v-lpg"),
    meat: document.getElementById("v-meat"),
    waste: document.getElementById("v-waste"),
    trees: document.getElementById("v-trees"),
  };
  const suffixes = {
    distance: " km",
    electricity: " kWh/mo",
    lpg: "/mo",
    meat: "/wk",
    waste: "/wk",
    trees: "",
  };

  if (sliders.distance) {
    let debounceTimer = null;

    function updateLabels() {
      labels.distance.textContent = sliders.distance.value + suffixes.distance;
      labels.electricity.textContent = sliders.electricity.value + suffixes.electricity;
      labels.lpg.textContent = sliders.lpg.value + suffixes.lpg;
      labels.meat.textContent = sliders.meat.value + suffixes.meat;
      labels.waste.textContent = sliders.waste.value + suffixes.waste;
      labels.trees.textContent = sliders.trees.value + suffixes.trees;
    }

    function buildPayload() {
      const p = initial.profile;
      return {
        transport_mode: p.transport_mode,
        distance_km: sliders.distance.value,
        fuel_type: p.fuel_type,
        electricity_kwh: sliders.electricity.value,
        lpg_cylinders: sliders.lpg.value,
        diet: p.diet,
        meat_meals_week: sliders.meat.value,
        waste_bag_size: p.waste_bag_size,
        waste_bags_week: sliders.waste.value,
        trees: sliders.trees.value,
        practices: p.practices,
      };
    }

    async function recompute() {
      const payload = buildPayload();
      try {
        const res = await fetch("/api/whatif", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        const net = data.result.net;
        document.getElementById("w-net").textContent = net + " kg CO\u2082e/yr";

        const delta = net - initial.result.net;
        const deltaEl = document.getElementById("w-delta");
        const sign = delta > 0 ? "+" : "";
        deltaEl.textContent = `${sign}${delta.toFixed(1)} kg vs. your baseline`;
        deltaEl.className = "whatif-delta " + (delta > 0 ? "up" : "down");

        document.getElementById("net-headline").textContent = net;
        document.getElementById("percentile-value").textContent = data.percentile + "%";

        renderRingGauge(data.result, data.contributors);
        renderContributors(data.contributors);
      } catch (err) {
        console.error("What-if recompute failed:", err);
      }
    }

    Object.values(sliders).forEach((el) => {
      el.addEventListener("input", () => {
        updateLabels();
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(recompute, 150);
      });
    });

    updateLabels();
  }
})();