# Allgemeiner KI-Assistent – Agent-Prompt

# Teil B – Optimierter Agent-Prompt

Kopiere den folgenden Block vollständig in Cursor. Voraussetzung: Teil A liegt als `PRD.md` im geöffneten Projektstamm.

```text
Du bist Senior Python Engineer. Implementiere das in PRD.md spezifizierte MVP
vollständig: allgemeiner deutscher KI-Assistent mit Sitzungsgedächtnis und
echtem Streaming. Verbindlicher Stack: Python 3.14.8, Pydantic AI,
Gradio Blocks, OpenAI GPT-5 mini. Arbeite im vorhandenen Projekt.

ZIEL UND AUTORITÄT
- Lies PRD.md vollständig und beachte vorhandene Repository-Instruktionen.
- PRD.md definiert Anforderungen, Limits und Abnahmekriterien.
- Erstelle eine ausführbare Anwendung, keine bloße Anleitung oder Attrappe.
- Bestehende Arbeit erhalten. Keine destruktiven Git-Aktionen, kein Deployment,
  keine Veröffentlichung und keine echten kostenpflichtigen API-Aufrufe ohne
  explizite Aktivierung. Gib Secrets niemals aus.
- Triff reversible Detailentscheidungen selbst. Frage nur bei einem tatsächlichen
  Widerspruch oder einer Entscheidung, die Produktumfang oder Stack verändert.

PHASE 1 – TECHNISCHE PRÜFUNG
1. Prüfe Projektdateien, verfügbare Python-Version und uv.
2. Verifiziere Installation des gesamten Stacks unter exakt Python 3.14.8.
   Verwende stabile, kompatible Paketversionen und erstelle uv.lock.
3. Nutze ausschließlich offizielle, zu diesen Versionen passende Dokumentation.
   Prüfe Agenteninitialisierung, OpenAI-Adapter, run_stream, stream_text,
   History-/Usage-Zugriff, Gradio State/Queue/Event-Cancellation und Tests.
4. Verifiziere gpt-5-mini, aktuellen Deprecation-/Verfügbarkeitsstatus und gültige
   Modellsettings. Keine automatische Migration zu einem anderen Modell.
   temperature/top_p nicht ungeprüft setzen. Responses API bevorzugen.
5. Dokumentiere Python- und Paketversionen, Dokumentationslinks und API-Entscheidungen
   knapp. Nenne konkrete Blocker statt Kompatibilität zu behaupten.
6. Lege einen kurzen Implementierungsplan an und arbeite danach weiter.

PHASE 2 – KERN UND MEMORY
- Verwende die src/ai_assistant-Struktur aus PRD.md mit installierbarem Paket.
- Erzeuge Konfiguration mit Pydantic Settings; keine API-Aufrufe beim Import.
- Agent, UI, History-Verarbeitung und ChatService sauber trennen.
- Halte autoritative Pydantic-AI-History und UI-Darstellung getrennt.
- Verwende frischen SessionState je Sitzung. Kein globaler Benutzerverlauf.
- Memory bleibt flüchtig und sitzungsgebunden. Kein BrowserState, keine Datenbank.
- Trim nur ganze abgeschlossene Runden. Instruktionen behalten. Neue Frage genau
  einmal übergeben; finale History weder verdoppeln noch durch UI-Text ersetzen.

PHASE 3 – STREAMING UND KOORDINATION
- Implementiere asynchrones echtes Pydantic-AI-Streaming als Service-Iterator
  mit typisierten Ereignissen und einem Gradio-Async-Generator als Adapter.
- Bevorzuge kumulative Textupdates. Prüfe die versionsspezifische Besonderheit
  von stream_text(delta=True) und belege vollständige finale History durch Test.
- Erst nach erfolgreichem Abschluss Frage und finale Antwort atomar committen.
- Je Sitzung nur ein aktiver Lauf; andere Sitzungen können parallel arbeiten.
- Lauf-ID plus Generation/Revision verhindert späte Updates nach Neuer Chat.
- Stop und Reset schließen Ressourcen und geben UI/Busy-Status zuverlässig frei.
- Abgebrochener/fehlgeschlagener Teiltext bleibt ausschließlich markierte Anzeige.
- finally-Cleanup auch bei CancelledError; Cancellation nicht als normalen
  Providerfehler verschlucken. Prüfe die konkrete Cancellation-Semantik von Gradio.
- Für nicht deepcopy-fähige Tasks/Locks ein aufgeräumtes Laufzeitregister verwenden,
  falls nötig; keine unbegrenzt wachsenden globalen Registries.
- Setze Eingabe-, Kontext-, Ausgabe-, Queue-, Parallelitäts- und Gesamttimeout-Limits.
- Retries nur vor erstem sichtbaren Chunk, begrenzt und abgestimmt mit SDK-Retries.

PHASE 4 – UI UND SICHERHEIT
- Implementiere die deutschen Komponenten und Status-/Memory-Hinweise aus PRD.md.
- Senden, Stoppen und Neuer Chat müssen auch bei Fehlern konsistent funktionieren.
- Starte auf 127.0.0.1 mit share=False. Keine öffentliche Bereitstellung.
- Sicheres Markdown; keine Ausführung generierter Inhalte oder Tools im MVP.
- Redigiere Exceptions und Logs. Keine Keys, Nachrichten oder HTTP-Bodies loggen.
- Verwende nur tatsächliche Usage-Metadaten; fehlende Werte nicht erfinden.

PHASE 5 – VERIFIKATION
- Offline-Tests ohne echte API-Aufrufe; dokumentierte Pydantic-AI-Testmechanismen
  oder deterministische Fakes einsetzen und reale Modellrequests verbieten.
- Decke alle Pflichttests und AC-01 bis AC-13 aus PRD.md ab. Besonders:
  vollständige History nach Streaming, isolierte interleavte Sessions,
  Doppelsenden, Reset vor Commit, Stop nach Teiltext, Cleanup, Retrygrenzen.
- Prüfe Memory anhand der Modellnachrichten, nicht anhand zufälliger LLM-Sätze.
- Führe uv run ruff check ., uv run ruff format --check . und uv run pytest aus.
  Behebe Fehler und wiederhole betroffene Checks.
- Füge CI für Python 3.14.8 und eingefrorenes Lockfile hinzu.
- Prüfe UI-Start und Eventverdrahtung ohne OpenAI-Aufruf. Manuellen Browsercheck
  durchführen, wenn die Umgebung dies ermöglicht.
- Livecheck nur nach expliziter Aktivierung mit vorhandenem Key. Ohne Livecheck
  Providerkonnektivität als unbestätigt ausweisen, nicht als erfolgreich getestet.

PHASE 6 – DOKUMENTATION UND ABSCHLUSS
- Liefere README.md, .env.example, .gitignore, pyproject.toml, uv.lock und Anwendung.
- Dokumentiere exakte Installationsschritte, Start mit
  uv run python -m ai_assistant, Tests, Limits und bekannte Einschränkungen.
- Weise insbesondere auf flüchtiges Memory, Kontext-Trimming, Anbieterübertragung,
  Modellstatus und mögliche Kosten trotz Abbruch hin.
- Gib eine kompakte Abnahmematrix: AC-ID, zugehöriger Test/manueller Check,
  bestanden/nicht ausgeführt/blockiert plus Grund.
- Abschließend: erstellte/geänderte Dateien, wirklich ausgeführte Checks,
  Startanleitung und verbleibende Blocker. Keine erfundenen Testergebnisse.

BEGINNE JETZT
Lies PRD.md und Repository-Instruktionen, prüfe die Umgebung und setze dann das
MVP schrittweise bis zur dokumentierten Abnahme um.
```
