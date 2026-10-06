# Sicherheit

## Schwachstelle melden

Bitte **keine öffentlichen Issues** für Sicherheitslücken anlegen. Stattdessen
über GitHub melden: Reiter **Security** → **Report a vulnerability**
(Private Vulnerability Reporting). Ich melde mich so bald wie möglich.

## Unterstützte Versionen

Sicherheitskorrekturen gibt es nur für die jeweils neueste Version
(siehe [Releases](../../releases)).

## Was bereits passiert

- Trivy prüft in jeder Pipeline die Abhängigkeiten, das Image und das Helm-Chart.
  Behebbare CRITICAL/HIGH-Funde lassen den Build scheitern.
- Dependabot hält Actions, Python-Pakete und das Basis-Image aktuell.
- Das Image basiert auf Wolfi, läuft als Non-root mit read-only Root-FS.
