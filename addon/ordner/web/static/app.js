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

  // --- upload, scherm 1: bestanden verzamelen (pakket 29, 30, 32) -----------
  // Het browserveld vervangt bij elke keuze zijn selectie (op de iPhone geeft "Maak foto" er één per keer).
  // De pagina houdt daarom zelf een lijst bij en schrijft die na elke wijziging terug in het veld `bestanden`
  // (DataTransfer), zodat required, de XHR-submit en de fallback hierboven ongewijzigd werken. Gelijke namen
  // (de camera noemt elke foto image.jpg) krijgen hier al `_2`, `_3`, … zoals `routes._unieke_namen`, en het
  // bestand gaat onder die naam mee: wat de lijst toont is wat op schijf komt. Zonder DataTransfer (oude
  // browsers) blijft het blok verborgen en werkt het veld zoals altijd; de server nummert dan zelf.
  const verzamel = form && form.querySelector("[data-verzamel]");
  if (verzamel) {
    let kan = false;
    try { kan = new DataTransfer().files.length === 0; } catch (_) { kan = false; }
    if (kan) {
      const veld = form.querySelector("input[name=bestanden]");
      const lijst = verzamel.querySelector("[data-gekozen]");
      let gekozen = [];
      const uniekeNaam = (naam, gezien) => {
        const punt = naam.lastIndexOf(".");
        const stam = punt > 0 ? naam.slice(0, punt) : naam, ext = punt > 0 ? naam.slice(punt) : "";
        let kandidaat = naam;
        for (let n = 2; gezien.has(kandidaat); n++) kandidaat = stam + "_" + n + ext;
        return kandidaat;
      };
      const toon = () => {
        const dt = new DataTransfer();
        const gezien = new Set();
        const namen = gekozen.map((f) => { const n = uniekeNaam(f.name, gezien); gezien.add(n); return n; });
        gekozen.forEach((f, i) => dt.items.add(namen[i] === f.name ? f : new File([f], namen[i], { type: f.type })));
        veld.files = dt.files;
        lijst.textContent = "";
        gekozen.forEach((f, i) => {
          const li = document.createElement("li");
          const naam = document.createElement("span");
          naam.className = "bestand-naam"; naam.textContent = namen[i];
          const verwijder = document.createElement("button");
          verwijder.type = "button"; verwijder.className = "verwijder"; verwijder.textContent = "×";
          verwijder.setAttribute("aria-label", "Verwijder");
          verwijder.addEventListener("click", () => { gekozen.splice(i, 1); toon(); });
          li.append(naam, verwijder);
          lijst.appendChild(li);
        });
      };
      // Het hoofdveld vervangt bij een nieuwe keuze zijn selectie; wij voegen toe aan wat er al was.
      veld.addEventListener("change", () => { gekozen = gekozen.concat(Array.from(veld.files)); toon(); });
      // Pakket 30: de knop klikt het browserveld aan, dat in het formulier blijft maar visueel verborgen is (CSS).
      verzamel.querySelector("[data-bestanden-kiezen]").addEventListener("click", () => veld.click());
      form.classList.add("verzamelt");
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
