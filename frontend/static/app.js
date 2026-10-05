// Bewusst minimal: keine Abhängigkeiten, alles funktioniert auch ohne JS.
document.addEventListener("DOMContentLoaded", () => {
  // Sicherheitsabfrage vor Löschen o. Ä.
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Filter sofort anwenden
  document.querySelectorAll("form[data-auto-submit]").forEach((form) => {
    form.querySelectorAll("select").forEach((el) => el.addEventListener("change", () => form.submit()));
  });

  // Etikett drucken
  document.querySelectorAll("[data-print]").forEach((btn) => btn.addEventListener("click", () => window.print()));

  // Gewählte Fotos anzeigen (die Datei-Inputs selbst sind versteckt)
  document.querySelectorAll("input[data-dateiname]").forEach((input) => {
    input.addEventListener("change", () => {
      const form = input.closest("form");
      const namen = [...form.querySelectorAll("input[data-dateiname]")]
        .flatMap((i) => [...i.files].map((f) => f.name));
      const ziel = form.querySelector(".dateiname");
      if (ziel) ziel.textContent = namen.length ? `Ausgewählt: ${namen.join(", ")}` : "";
    });
  });

  // Doppeltes Absenden verhindern (schlechtes Netz am Schießstand)
  document.querySelectorAll("form[method=post]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented) return;
      form.querySelectorAll("button[type=submit]").forEach((b) => { b.disabled = true; });
    });
  });

  // Nach "Zurück" (bfcache) Buttons wieder freigeben
  window.addEventListener("pageshow", () => {
    document.querySelectorAll("button[type=submit]").forEach((b) => { b.disabled = false; });
  });
});
