# Allgemeiner KI-Assistent (MVP)

Ein lokaler, modularer KI-Assistent in deutscher Sprache mit Sitzungsgedächtnis und echtem Streaming auf Basis von **Pydantic AI**, **Gradio Blocks** und **OpenAI GPT-5 mini** unter **Python 3.14.8**.

---

## 1. Technischer Stack & Versionen

Die Implementierung wurde unter der exakten Python-Version 3.14.8 verifiziert und fest im Lockfile `uv.lock` verankert:

- **Python**: `3.14.8` (gepinnt in `.python-version` und `pyproject.toml`)
- **Pydantic AI**: `2.55.0`
- **Gradio**: `6.30.0`
- **Pydantic Settings**: `2.15.0`
- **OpenAI Python SDK**: `3.28.0`
- **Pytest**: `9.1.1`
- **Pytest-asyncio**: `1.4.0`
- **Ruff**: `0.17.0`
- **Paketmanager / Tooling**: `uv 0.13.0`

---

## 2. Installation und Einrichtung

### Voraussetzungen
- Python 3.14.8 installiert (oder automatische Bereitstellung durch `uv`)
- `uv` installiert

### Schritt-für-Schritt-Installation

1. **Repository klonen / Verzeichnis öffnen**:
   ```powershell
   cd "C:\Users\andre\Documents\AI mit Arnie\Test Antigravity\Chatbot"
   ```

2. **Abhängigkeiten synchronisieren**:
   ```powershell
   uv sync --frozen --python 3.14.8
   ```

3. **Umgebungskonfiguration anlegen**:
   Kopiere `.env.example` nach `.env` und wähle deinen Modellanbieter:

   ```powershell
   copy .env.example .env
   ```

   **Option A: Groq Cloud (Kostenlos, sehr hohes Kontingent: 1.000+ Anfragen/Tag)**
   > Einen kostenlosen API-Key erhältst du unter: [console.groq.com/keys](https://console.groq.com/keys)
   ```dotenv
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=openai/gpt-oss-120b
   ```

   **Option B: Google Gemini (Kostenloser Free Tier)**
   > Einen kostenlosen API-Key erhältst du unter: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   ```dotenv
   LLM_PROVIDER=google
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```

   **Option C: OpenAI (Standard)**
   ```dotenv
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-5-mini
   ```

---

## 3. Anwendung ausführen

Starte die Anwendung lokal über `uv`:
```powershell
uv run python -m ai_assistant
```
Die Benutzeroberfläche öffnet sich lokal unter:
[http://127.0.0.1:7860](http://127.0.0.1:7860)

*Hinweis*: Die Anwendung bindet strikt an `127.0.0.1` mit `share=False`. Es werden keine öffentlichen Links oder Tunnel geöffnet.

---

## 4. Tests und Code-Qualität

Alle Unit- und Integrationstests laufen vollständig offline ohne echte Modell-Aufrufe über deterministische Fakes (`FunctionModel`):

```powershell
# Code-Formatierung prüfen
uv run ruff format --check .

# Linting prüfen
uv run ruff check .

# Testsuite ausführen
uv run pytest -v
```

---

## 5. Hinweise zu Memory, Limits und Modellstatus

- **Sitzungsgedächtnis (Flüchtiges Memory)**:
  - Das Gesprächsgedächtnis existiert ausschließlich serverseitig für die Dauer der aktuellen Browser-Sitzung.
  - Es erfolgt **keine** Persistierung in SQLite, JSON-Dateien oder Browser LocalStorage.
  - Das Schließen des Browser-Tabs oder ein Klick auf **„Neuer Chat“** löscht den Verlauf logisch vollständig.
- **Kontext-Trimming**:
  - Überschreitet der Verlauf 20 Runden (`MAX_CONTEXT_TURNS`) oder 80.000 Zeichen (`MAX_CONTEXT_CHARS`), werden automatisch die ältesten vollständigen Frage-Antwort-Runden entfernt.
  - Die zentralen System-Instruktionen bleiben stets erhalten.
- **Abbruchverhalten (Stoppen)**:
  - Bei Klick auf **„Stoppen“** wird die lokale Verarbeitung sofort abgebrochen und die Eingabemöglichkeit freigegeben.
  - Teilantworten werden in der UI als abgebrochen markiert und **nicht** in das Modellgedächtnis übernommen.
  - Beim Modellanbieter (OpenAI) können für bereits verarbeitete Tokens trotz Abbruch Kosten anfallen.
- **Modellstatus `gpt-5-mini`**:
  - Das Modell `gpt-5-mini` wird über die moderne OpenAI Responses API angesprochen (`OpenAIResponsesModel`).
  - Laut OpenAI-Dokumentation ist das Modell derzeit als *Deprecated* markiert. Vor einem Produktiveinsatz sind Verfügbarkeit und Modellberechtigungen des OpenAI-Accounts zu prüfen.

---

## 6. Abnahmematrix (AC-01 bis AC-13)

| ID | Kriterium | Status | Verifikation / Nachweis |
|---|---|---|---|
| **AC-01** | **Installation** | Bestanden | `uv.lock` erfolgreich gegen Python 3.14.8 aufgelöst; Versionen in README und `uv.lock` dokumentiert. |
| **AC-02** | **Start** | Bestanden | `uv run python -m ai_assistant` startet; fehlender Key wirft sichere Fehlermeldung mit Exit-Code 1 ohne Traceback (`test_load_settings_missing_key`). |
| **AC-03** | **Streaming** | Bestanden | Test `test_deterministic_streaming_three_chunks` verifiziert mindestens 3 wachsende Chunks vor dem Abschluss. Echter Provider-Livecheck ist mangels Key als unbestätigt/nicht ausgeführt markiert. |
| **AC-04** | **Memory** | Bestanden | Test `test_memory_multi_turn_history` belegt, dass Folgerunden vorherige Fragen/Antworten genau einmal in `all_messages()` erhalten. |
| **AC-05** | **Isolation** | Bestanden | Test `test_session_isolation` belegt vollständige Isolation interleavter Sitzungen ohne Übersprechen. |
| **AC-06** | **Reset** | Bestanden | Test `test_reset_discards_active_run_and_clears_history` belegt Verwerfen laufender Chunks und vollständige Leerung nach „Neuer Chat“. |
| **AC-07** | **Abbruch** | Bestanden | Test `test_stop_releases_session_and_marks_partial` belegt sofortige Freigabe (< 2s) und Ausschluss von Teiltext aus Folgerunden. |
| **AC-08** | **Doppelsenden**| Bestanden | Test `test_prevent_concurrent_runs_in_same_session` blockiert konkurrierende Requests in derselben Sitzung (`ConcurrentRunError`). |
| **AC-09** | **Limits** | Bestanden | Tests `test_input_limits_and_validation` & `test_trim_context_turns_preserves_system_prompt` prüfen Eingabevalidierung und Runden-Trimming. |
| **AC-10** | **Fehler** | Bestanden | Test `test_classify_error_types` und `test_error_flow_in_chat_service` decken 401, 403/404, 429, Timeout und Verbindungsfehler sicher ab. |
| **AC-11** | **Sicherheit** | Bestanden | Tests `test_redact_secret_string`, `test_redacting_formatter` und `test_secret_redaction_in_repr` belegen vollständige Secret-Redaktion. Drittanbieter-Logging gedrosselt. |
| **AC-12** | **Qualität** | Bestanden | `ruff check .`, `ruff format --check .` und 20/20 `pytest`-Tests bestehen fehlerfrei unter Python 3.14.8. |
| **AC-13** | **Dokumentation**| Bestanden | README.md, PRD.md, .env.example, .gitignore und CI-Workflow vollständig vorhanden. |

---

## 7. Troubleshooting

- **Fehlermeldung `Konfigurationsfehler: Fehlende Konfiguration: OPENAI_API_KEY ...`**:
  - Trage deinen OpenAI API-Schlüssel in die Datei `.env` ein oder setze `$env:OPENAI_API_KEY="sk-..."` in deiner Powershell.
- **Port 7860 bereits belegt**:
  - Ändere `APP_PORT=7861` in der `.env`-Datei.
- **TLS-/Zertifikatsfehler bei uv-Aufrufen**:
  - Setze `$env:UV_SYSTEM_CERTS="true"`.
