document.addEventListener("DOMContentLoaded", () => {
  const statusUrl = document.body.dataset.statusUrl;
  const POLL_MS = 3000;

  // --- upload, scherm 1 (bestanden) met voortgangsbalk ---------------------
  // Na de upload leest de server de tekst en antwoordt met een redirect naar scherm 2 (gegevens);
  // responseURL bevat dat adres, inclusief het Ingress-prefix. Scherm 2 is een gewoon formulier zonder JS.
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
      xhr.upload.onload = () => {
        // Upload klaar; de server leest nu eerst de tekst (kan even duren): "Bestanden ontvangen, tekst lezen…".
        if (bar) bar.removeAttribute("value");
        const bezig = form.querySelector("[data-bezig]");
        if (bezig) bezig.hidden = false;
        form.querySelectorAll("button[type=submit]").forEach((b) => { b.disabled = true; });
      };
      xhr.onload = () => {
        if (xhr.status < 400 && xhr.responseURL) { window.location = xhr.responseURL; return; }  // door naar scherm 2
        // Validatiefout (400, geen bestanden): toon het teruggestuurde formulier zoals bij een gewone POST.
        document.open(); document.write(xhr.responseText); document.close();
      };
      xhr.onerror = () => form.submit();
      xhr.send(new FormData(form));
    });
  }

  // --- upload, scherm 1: foto's verzamelen (pakket 29) ----------------------
  // Op de iPhone levert "Foto maken" één foto en vervangt een tweede keuze de eerste. De pagina houdt
  // daarom zelf een lijst bij en schrijft die na elke wijziging terug in het veld `bestanden`
  // (DataTransfer), zodat required, de XHR-submit en de fallback hierboven ongewijzigd werken.
  // Zonder DataTransfer (oude browsers) blijft het blok verborgen en werkt het veld zoals altijd.
  const verzamel = form && form.querySelector("[data-verzamel]");
  if (verzamel) {
    let kan = false;
    try { kan = new DataTransfer().files.length === 0; } catch (_) { kan = false; }
    if (kan) {
      const veld = form.querySelector("input[name=bestanden]");
      const camera = verzamel.querySelector("[data-camera]");
      const lijst = verzamel.querySelector("[data-gekozen]");
      let gekozen = [];
      const toon = () => {
        const dt = new DataTransfer();
        gekozen.forEach((f) => dt.items.add(f));
        veld.files = dt.files;
        lijst.textContent = "";
        gekozen.forEach((f, i) => {
          const li = document.createElement("li");
          const naam = document.createElement("span");
          naam.className = "bestand-naam"; naam.textContent = f.name;
          const weg = document.createElement("button");
          weg.type = "button"; weg.className = "als-link weg"; weg.textContent = "Weg";
          weg.addEventListener("click", () => { gekozen.splice(i, 1); toon(); });
          li.append(naam, weg);
          lijst.appendChild(li);
        });
      };
      // Het hoofdveld vervangt bij een nieuwe keuze zijn selectie; wij voegen toe aan wat er al was.
      veld.addEventListener("change", () => { gekozen = gekozen.concat(Array.from(veld.files)); toon(); });
      camera.addEventListener("change", () => { gekozen = gekozen.concat(Array.from(camera.files)); camera.value = ""; toon(); });
      verzamel.querySelector("[data-foto-maken]").addEventListener("click", () => camera.click());
      verzamel.hidden = false;
    }
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
        zet("inbox-totaal", s.inbox.totaal);
        zet("inbox-wachtend", s.inbox.wachtend);
        zet("inbox-dubbel", s.inbox.dubbel);
        zet("prullenbak-aantal", s.prullenbak.aantal);
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
