const API = "http://127.0.0.1:8000";

let selectedId = null;

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function show(id, text) {
  document.getElementById(id).textContent = typeof text === "string" ? text : JSON.stringify(text, null, 2);
}

async function loadDisputes() {
  const data = await api("/api/disputes?limit=50");
  const list = document.getElementById("disputeList");
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
}

async function openDispute(transactionId) {
  selectedId = transactionId;
  const d = await api(`/api/disputes/${transactionId}`);
  document.getElementById("detailSection").hidden = false;

  document.getElementById("detailMeta").innerHTML = `
    <p><strong>${d.product_name}</strong></p>
    <p>Seller: ${d.seller_name}</p>
    <p>Reason: ${d.dispute_reason} | Status: <span class="badge">${d.status}</span></p>
  `;

  const grid = document.getElementById("imageGrid");
  grid.innerHTML = "";
  for (const [type, items] of Object.entries(d.images)) {
    for (const img of items) {
      const box = document.createElement("div");
      box.className = "image-box";
      box.innerHTML = `<p><strong>${type.toUpperCase()}</strong></p>`;
      if (img.url) {
        const image = document.createElement("img");
        image.src = `${API}${img.url}`;
        box.appendChild(image);
      } else {
        box.innerHTML += `<small>${img.source_url.slice(0, 60)}...</small>`;
      }
      grid.appendChild(box);
    }
  }

  if (d.latest_analysis) {
    show("analysisResult", d.latest_analysis);
    const pct = d.latest_analysis.compensation?.recommended_pct;
    if (pct != null) document.getElementById("reviewPct").value = pct;
  } else {
    show("analysisResult", "No analysis yet.");
  }
}

document.getElementById("uploadBtn").onclick = async () => {
  const file = document.getElementById("excelFile").files[0];
  if (!file) return alert("Choose an Excel file first");
  const form = new FormData();
  form.append("file", file);
  try {
    const data = await api("/api/disputes/upload", { method: "POST", body: form });
    show("uploadResult", data);
    loadDisputes();
  } catch (e) {
    show("uploadResult", e.message);
  }
};

document.getElementById("refreshBtn").onclick = loadDisputes;
document.getElementById("downloadAllBtn").onclick = async () => {
  show("uploadResult", await api("/api/disputes/download-all?limit=5", { method: "POST" }));
  loadDisputes();
};
document.getElementById("analyzeAllBtn").onclick = async () => {
  show("uploadResult", await api("/api/disputes/analyze-all?limit=5", { method: "POST" }));
  loadDisputes();
};

document.getElementById("downloadBtn").onclick = async () => {
  if (!selectedId) return;
  show("analysisResult", await api(`/api/disputes/${selectedId}/download-images`, { method: "POST" }));
  openDispute(selectedId);
};

document.getElementById("analyzeBtn").onclick = async () => {
  if (!selectedId) return;
  const data = await api(`/api/disputes/${selectedId}/analyze`, { method: "POST" });
  show("analysisResult", data.result);
  loadDisputes();
};

document.getElementById("saveReviewBtn").onclick = async () => {
  if (!selectedId) return;
  const body = {
    decision: document.getElementById("reviewDecision").value,
    final_compensation_pct: Number(document.getElementById("reviewPct").value),
    notes: document.getElementById("reviewNotes").value,
  };
  show("analysisResult", await api(`/api/disputes/${selectedId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
  openDispute(selectedId);
};

loadDisputes().catch((e) => show("uploadResult", e.message));
