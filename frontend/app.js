const API = "http://127.0.0.1:8000";

let selectedId = null;

function formatError(err) {
  if (!err) return "Unknown error";
  if (typeof err === "string") return err;
  if (Array.isArray(err)) return err.map((e) => e.msg || JSON.stringify(e)).join(", ");
  return String(err);
}

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API}${path}`, options);
  } catch (e) {
    throw new Error(
      "Cannot reach backend. Start it with: uvicorn backend.app.main:app --reload --port 8000"
    );
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(formatError(data.detail || data.message || res.statusText));
  return data;
}

function show(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  if (typeof text === "string") {
    el.textContent = text;
  } else {
    el.textContent = "Result available (see console)";
    console.log("UI_RESULT", id, text);
  }
}

function setStatus(text) {
  document.getElementById("listStatus").textContent = text;
}

async function withLoading(button, message, fn) {
  const oldText = button.textContent;
  button.disabled = true;
  button.textContent = "Please wait...";
  setStatus(message);
  try {
    return await fn();
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

async function loadDisputes() {
  const data = await api("/api/disputes?limit=50");
  const list = document.getElementById("disputeList");

  if (!data.items.length) {
    list.innerHTML = "<p class='hint'>No disputes yet. Upload the Excel file first.</p>";
    setStatus("0 disputes found");
    return;
  }

  list.innerHTML = data.items
    .map(
      (d) => `
      <div class="dispute-item" data-id="${d.transaction_id}">
        <strong>${d.transaction_id}</strong>
        <span class="badge">${d.status}</span>
        <div>${d.dispute_reason} — ${d.product_name}</div>
      </div>`
    )
    .join("");

  list.querySelectorAll(".dispute-item").forEach((el) => {
    el.onclick = () => openDispute(el.dataset.id);
  });

  setStatus(`${data.total} disputes loaded. Click one to see details.`);
}

async function openDispute(transactionId) {
  selectedId = transactionId;
  const d = await api(`/api/disputes/${transactionId}`);
  const section = document.getElementById("detailSection");
  section.hidden = false;
  section.scrollIntoView({ behavior: "smooth" });

  document.getElementById("detailMeta").innerHTML = `
    <p><strong>${d.product_name}</strong></p>
    <p>Seller: ${d.seller_name}</p>
    <p>Reason: ${d.dispute_reason} | Status: <span class="badge">${d.status}</span></p>
  `;

  const grid = document.getElementById("imageGrid");
  grid.innerHTML = "";
  let imageCount = 0;

  for (const [type, items] of Object.entries(d.images)) {
    for (const img of items) {
      imageCount += 1;
      const box = document.createElement("div");
      box.className = "image-box";
      box.innerHTML = `<p><strong>${type.toUpperCase()}</strong></p>`;
      if (img.url) {
        const image = document.createElement("img");
        image.src = `${API}${img.url}`;
        image.alt = type;
        image.onerror = () => {
          box.innerHTML += `<small>Image failed to load</small>`;
        };
        box.appendChild(image);
      } else {
        box.innerHTML += `<small>Not downloaded yet<br>${(img.source_url || "").slice(0, 80)}</small>`;
      }
      grid.appendChild(box);
    }
  }

  if (imageCount === 0) {
    grid.innerHTML = "<p class='hint'>No images for this dispute.</p>";
  }

  if (d.latest_analysis) {
    show("analysisResult", d.latest_analysis);
    const pct = d.latest_analysis.compensation?.recommended_pct;
    if (pct != null) document.getElementById("reviewPct").value = pct;
  } else {
    show("analysisResult", "No analysis yet. Click 'Download images' then 'Run analysis'.");
  }
}

document.getElementById("uploadBtn").onclick = async () => {
  const file = document.getElementById("excelFile").files[0];
  if (!file) return alert("Choose SHD_Dispute_data.xlsx first");
  const btn = document.getElementById("uploadBtn");
  try {
    await withLoading(btn, "Uploading Excel...", async () => {
      const form = new FormData();
      form.append("file", file);
      const data = await api("/api/disputes/upload", { method: "POST", body: form });
      show("uploadResult", data);
      await loadDisputes();
    });
  } catch (e) {
    show("uploadResult", e.message);
  }
};

document.getElementById("refreshBtn").onclick = async () => {
  try {
    await loadDisputes();
  } catch (e) {
    show("uploadResult", e.message);
  }
};

document.getElementById("downloadAllBtn").onclick = async () => {
  const btn = document.getElementById("downloadAllBtn");
  try {
    await withLoading(btn, "Downloading images for 5 disputes (may take 1 minute)...", async () => {
      const data = await api("/api/disputes/download-all?limit=5", { method: "POST" });
      show("uploadResult", data);
      await loadDisputes();
    });
  } catch (e) {
    show("uploadResult", e.message);
  }
};

document.getElementById("analyzeAllBtn").onclick = async () => {
  const btn = document.getElementById("analyzeAllBtn");
  try {
    await withLoading(btn, "Running analysis on 5 disputes...", async () => {
      const data = await api("/api/disputes/analyze-all?limit=5", { method: "POST" });
      show("uploadResult", data);
      await loadDisputes();
    });
  } catch (e) {
    show("uploadResult", e.message);
  }
};

document.getElementById("downloadBtn").onclick = async () => {
  if (!selectedId) return alert("Select a dispute first");
  const btn = document.getElementById("downloadBtn");
  try {
    await withLoading(btn, "Downloading images...", async () => {
      const data = await api(`/api/disputes/${selectedId}/download-images`, { method: "POST" });
      show("analysisResult", data);
      await openDispute(selectedId);
    });
  } catch (e) {
    show("analysisResult", e.message);
  }
};

document.getElementById("analyzeBtn").onclick = async () => {
  if (!selectedId) return alert("Select a dispute first");
  const btn = document.getElementById("analyzeBtn");
  try {
    await withLoading(btn, "Running analysis...", async () => {
      const data = await api(`/api/disputes/${selectedId}/analyze`, { method: "POST" });
      show("analysisResult", data.result);
      await loadDisputes();
      await openDispute(selectedId);
    });
  } catch (e) {
    show("analysisResult", e.message);
  }
};

document.getElementById("saveReviewBtn").onclick = async () => {
  if (!selectedId) return alert("Select a dispute first");
  const btn = document.getElementById("saveReviewBtn");
  try {
    await withLoading(btn, "Saving review...", async () => {
      const body = {
        decision: document.getElementById("reviewDecision").value,
        final_compensation_pct: Number(document.getElementById("reviewPct").value),
        notes: document.getElementById("reviewNotes").value,
      };
      const data = await api(`/api/disputes/${selectedId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      show("analysisResult", data);
      await openDispute(selectedId);
    });
  } catch (e) {
    show("analysisResult", e.message);
  }
};

loadDisputes().catch((e) => {
  show("uploadResult", e.message);
  setStatus("Failed to load disputes");
});
