document.addEventListener("DOMContentLoaded", () => {
  const statusUrl = document.body.dataset.statusUrl;
  const POLL_MS = 3000;

  // --- upload met voortgangsbalk ---------------------------------------
  const form = document.querySelector("form[data-upload]");
  if (form && window.XMLHttpRequest) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const bar = form.querySelector("progress");
      if (bar) bar.hidden = false;
      const xhr = new XMLHttpRequest();
      xhr.open("POST", form.action);
      xhr.upload.onprogress = (ev) => {
        if (bar && ev.lengthComputable) { bar.max = ev.total; bar.value = ev.loaded; }
      };
      xhr.onload = () => {
        if (xhr.status < 400 && xhr.responseURL) { window.location = xhr.responseURL; return; }
        // Validatiefout (400): toon het teruggestuurde formulier zoals bij een gewone POST.
        document.open(); document.write(xhr.responseText); document.close();
      };
      xhr.onerror = () => form.submit();
      xhr.send(new FormData(form));
    });
  }

  if (!statusUrl || !window.fetch) return;

  // --- documentpagina: herladen zodra OCR klaar is ---------------------
  const pending = document.querySelector('section[data-ocr="pending"]');
  if (pending) {
    const rel = pending.dataset.rel;
    const poll = async () => {
      try {
        const r = await fetch(statusUrl + "?rel=" + encodeURIComponent(rel), { cache: "no-store" });
        if (!r.ok) return;
        const s = await r.json();
        if (s.ocr === "done" || s.ocr === "failed") { location.reload(); return; }
      } catch (_) { /* volgende poll probeert opnieuw */ }
      setTimeout(poll, POLL_MS);
    };
    setTimeout(poll, POLL_MS);
  }

  // --- beheerpagina: tellingen live bijwerken ---------------------------
  const beheer = document.querySelector("[data-beheer]");
  if (beheer) {
    let reconcileWasBezig = beheer.querySelector('[data-tel="reconcile"]')?.textContent.trim() === "bezig";
    const zet = (naam, waarde) => {
      const el = beheer.querySelector('[data-tel="' + naam + '"]');
      if (el) el.textContent = waarde;
    };
    const poll = async () => {
      try {
        const r = await fetch(statusUrl, { cache: "no-store" });
        if (!r.ok) return;
        const s = await r.json();
        for (const k of ["totaal", "pending", "done", "failed"]) zet(k, s.tellingen[k]);
        zet("queue", s.queue);
        zet("reconcile", s.reconcile_bezig ? "bezig" : "niet bezig");
        const lijst = beheer.querySelector("[data-bezig]");
        if (lijst) {
          lijst.textContent = "";
          if (s.bezig.length === 0) {
            const li = document.createElement("li");
            li.className = "leeg"; li.textContent = "Niets.";
            lijst.appendChild(li);
          }
          for (const [rel, naam] of s.bezig) {
            const li = document.createElement("li");
            li.textContent = rel + "/" + naam;
            lijst.appendChild(li);
          }
        }
        if (reconcileWasBezig && !s.reconcile_bezig) { location.reload(); return; }
        reconcileWasBezig = s.reconcile_bezig;
      } catch (_) { /* volgende poll probeert opnieuw */ }
      setTimeout(poll, POLL_MS);
    };
    setTimeout(poll, POLL_MS);
  }
});
