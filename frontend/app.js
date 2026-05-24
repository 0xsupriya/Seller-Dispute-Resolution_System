const API = "http://127.0.0.1:8000";

let selectedId = null;

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API}${path}`, options);
  } catch (e) {
    throw new Error("Backend unavailable. Start with: uvicorn backend.app.main:app --port 8000");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || data.message || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function loadDisputes() {
  try {
    const data = await api("/api/disputes?limit=50");
    const list = document.getElementById("disputeList");

    if (!data.items.length) {
      list.innerHTML = "<p class='hint'>No disputes found.</p>";
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
  } catch (e) {
    alert("Error loading disputes: " + e.message);
  }
}

async function openDispute(transactionId) {
  try {
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
            box.innerHTML += `<small>Failed to load</small>`;
          };
          box.appendChild(image);
        } else {
          box.innerHTML += `<small>Not downloaded</small>`;
        }
        grid.appendChild(box);
      }
    }

    if (imageCount === 0) {
      grid.innerHTML = "<p class='hint'>No images.</p>";
    }

    if (d.latest_analysis) {
      const pct = d.latest_analysis.compensation?.recommended_pct;
      if (pct != null) document.getElementById("reviewPct").value = pct;
    }
  } catch (e) {
    alert("Error loading dispute: " + e.message);
  }
}

document.getElementById("downloadBtn").onclick = async () => {
  if (!selectedId) return alert("Select a dispute first");
  const btn = document.getElementById("downloadBtn");
  btn.disabled = true;
  try {
    await api(`/api/disputes/${selectedId}/download-images`, { method: "POST" });
    alert("Images downloaded");
    await openDispute(selectedId);
  } catch (e) {
    alert("Download failed: " + e.message);
  } finally {
    btn.disabled = false;
  }
};

document.getElementById("analyzeBtn").onclick = async () => {
  if (!selectedId) return alert("Select a dispute first");
  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true;
  try {
    const data = await api(`/api/disputes/${selectedId}/analyze`, { method: "POST" });
    alert("Analysis complete");
    await openDispute(selectedId);
  } catch (e) {
    alert("Analysis failed: " + e.message);
  } finally {
    btn.disabled = false;
  }
};

document.getElementById("saveReviewBtn").onclick = async () => {
  if (!selectedId) return alert("Select a dispute first");
  const btn = document.getElementById("saveReviewBtn");
  btn.disabled = true;
  try {
    const body = {
      decision: document.getElementById("reviewDecision").value,
      final_compensation_pct: Number(document.getElementById("reviewPct").value),
      notes: document.getElementById("reviewNotes").value,
    };
    await api(`/api/disputes/${selectedId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    alert("Review saved");
    await openDispute(selectedId);
  } catch (e) {
    alert("Save failed: " + e.message);
  } finally {
    btn.disabled = false;
  }
};

loadDisputes();
