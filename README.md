# Transcriptor

System do automatycznej transkrypcji nagrań z call center. Monitoruje folder z nagraniami WAV, transkrybuje je za pomocą Whisper, rozdziela mówców (pyannote) i klasyfikuje kto jest agentem, a kto klientem. Posiada webowy dashboard oraz CLI.

## Wymagania systemowe

- **Python** >= 3.10
- **Node.js** >= 18 (dla frontendu)
- **FFmpeg** — wymagany przez pydub do obsługi plików audio
- **HuggingFace token** — wymagany przez pyannote do diaryzacji mówców
- ~4 GB RAM (Whisper large-v3 na CPU) lub GPU z CUDA dla szybszej transkrypcji

### Instalacja FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (choco)
choco install ffmpeg
```

### Token HuggingFace (wymagany)

Pyannote wymaga tokenu HuggingFace. Najpierw zaakceptuj warunki modeli:
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

Następnie wygeneruj token: https://huggingface.co/settings/tokens

## Instalacja

```bash
# Klonuj repozytorium
git clone <repo-url>
cd rec-conv-transcriptor

# Zainstaluj wszystko (Python + Node.js)
make install
```

Lub ręcznie:

```bash
# Backend (Python)
pip install -e .

# Frontend (React)
cd frontend && npm install
```

## Konfiguracja

Utwórz plik `.env` w katalogu głównym projektu:

```env
# WYMAGANE - token HuggingFace do pyannote
PYANNOTE_AUTH_TOKEN=hf_twoj_token

# Folder z nagraniami WAV (domyślnie ~/Downloads/NAGRANIA)
WATCH_DIR=/sciezka/do/nagran

# Baza danych (domyślnie SQLite w katalogu projektu)
DATABASE_URL=sqlite:///transcriptions.db

# Model Whisper: tiny, base, small, medium, large-v3
# large-v3 = najlepsza jakość, wolniejszy na CPU
# small = dobry kompromis szybkość/jakość
WHISPER_MODEL_SIZE=large-v3

# Urządzenie: auto, cpu, cuda
WHISPER_DEVICE=auto

# Typ obliczeń: float16 (GPU), int8 (CPU), float32
WHISPER_COMPUTE_TYPE=float16

# Język nagrań (domyślnie polski)
WHISPER_LANGUAGE=pl

# Poziom logowania: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

## Uruchamianie

### Dashboard webowy (zalecane)

```bash
# Tryb produkcyjny — buduje frontend i startuje serwer
make build
make start
# Dashboard dostępny na http://localhost:8000
```

```bash
# Tryb deweloperski — hot reload backend + frontend
make dev
# Frontend: http://localhost:5173 (z proxy do API)
# Backend API: http://localhost:8000
```

### Uruchamianie w tle (serwer + watcher)

```bash
# Uruchom dashboard w tle
nohup python3 -m transcriptor serve --port 8000 > logs/server.log 2>&1 &

# Uruchom watcher w tle (automatyczne przetwarzanie nowych plików)
nohup python3 -m transcriptor watch > logs/watcher.log 2>&1 &

# Sprawdź czy działają
ps aux | grep transcriptor

# Zatrzymaj
kill $(pgrep -f "transcriptor serve")
kill $(pgrep -f "transcriptor watch")
```

Lub za pomocą systemd (Linux):

```bash
# Skopiuj plik serwisu (przykład)
sudo tee /etc/systemd/system/transcriptor.service << 'EOF'
[Unit]
Description=Transcriptor Dashboard
After=network.target

[Service]
Type=simple
User=twoj_user
WorkingDirectory=/sciezka/do/rec-conv-transcriptor
ExecStart=/usr/bin/python3 -m transcriptor serve --port 8000
Restart=always
RestartSec=5
Environment=PYANNOTE_AUTH_TOKEN=hf_twoj_token

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable transcriptor
sudo systemctl start transcriptor
```

### CLI (linia poleceń)

```bash
# Przetwórz pojedynczy plik
python3 -m transcriptor process /sciezka/do/nagrania.wav

# Przetwórz wszystkie nieprzetworzone pliki z folderu WATCH_DIR
python3 -m transcriptor process-all

# Uruchom watcher (monitoruje folder, przetwarza nowe pliki automatycznie)
python3 -m transcriptor watch

# Wyświetl transkrypcję
python3 -m transcriptor query <recording_id>

# Szukaj w transkrypcjach
python3 -m transcriptor search "szukana fraza"

# Lista wszystkich nagrań
python3 -m transcriptor list

# Statystyki
python3 -m transcriptor stats

# Zamień etykiety agent/klient (jeśli detekcja się pomyliła)
python3 -m transcriptor swap-speakers <recording_id>

# Uruchom dashboard webowy
python3 -m transcriptor serve [--host 0.0.0.0] [--port 8000] [--reload]
```

## Jak działa system

### Pipeline transkrypcji

1. **Detekcja audio** — sprawdza czy nagranie jest stereo czy mono
2. **Stereo** — rozdziela kanały (lewy = agent, prawy = klient) — standard call center
3. **Mono** — uruchamia diaryzację pyannote (identyfikacja 2 mówców)
4. **Transkrypcja** — Whisper transkrybuje mowę na tekst z timestampami
5. **Klasyfikacja mówców** — heurystyka wielosygnałowa rozpoznaje kto jest agentem:
   - Formalne/sprzedażowe frazy (agent mówi "dzień dobry, dzwonię z...", "mogę zaproponować", ceny, dane dostawy)
   - Krótkie odpowiedzi klienta ("tak", "nie", "no niech będzie", "mhm")
   - Czas mówienia (agent mówi więcej)
   - Średnia długość wypowiedzi (agent ma dłuższe segmenty)
6. **Zapis** — wyniki trafiają do bazy SQLite

### Dashboard webowy

- **Panel główny** — statystyki, wykres nagrań, ostatnie nagrania
- **Lista nagrań** — tabela z filtrowaniem, sortowaniem, uploadem plików
- **Szczegóły nagrania** — odtwarzacz audio z waveformem, transkrypcja z kolorami mówców, timeline, eksport (TXT/SRT/JSON)
- **Wyszukiwanie** — pełnotekstowe po wszystkich transkrypcjach
- **Pipeline** — sterowanie watcherem, status przetwarzania

### API REST

Dashboard komunikuje się przez FastAPI (port 8000):

| Endpoint | Opis |
|----------|------|
| `GET /api/recordings` | Lista nagrań (paginacja, filtrowanie) |
| `GET /api/recordings/{id}` | Nagranie z transkrypcją i segmentami |
| `GET /api/recordings/{id}/audio` | Streaming pliku WAV |
| `POST /api/recordings/upload` | Upload nowego nagrania |
| `POST /api/recordings/{id}/reprocess` | Ponowna transkrypcja |
| `DELETE /api/recordings/{id}` | Usunięcie nagrania |
| `GET /api/search?q=tekst` | Wyszukiwanie w transkrypcjach |
| `GET /api/stats` | Statystyki dashboardu |
| `GET /api/pipeline/status` | Status watchera |
| `POST /api/pipeline/start` | Start watchera |
| `POST /api/pipeline/stop` | Stop watchera |
| `WS /ws/progress` | WebSocket — postęp przetwarzania na żywo |

## Struktura projektu

```
rec-conv-transcriptor/
├── src/transcriptor/           # Backend Python
│   ├── __main__.py             # Entry point: python -m transcriptor
│   ├── main.py                 # CLI (Click) — watch, process, serve, query...
│   ├── config.py               # Konfiguracja (.env)
│   ├── pipeline.py             # Pipeline: audio → diaryzacja → transkrypcja → klasyfikacja
│   ├── api/
│   │   ├── server.py           # FastAPI REST API + WebSocket
│   │   └── query.py            # Zapytania do bazy danych
│   ├── db/
│   │   ├── models.py           # SQLAlchemy: Recording, Transcript, Segment, Speaker
│   │   └── database.py         # Silnik i sesja bazy danych
│   ├── transcriber/
│   │   └── whisper_service.py  # Wrapper Whisper (faster-whisper)
│   ├── diarizer/
│   │   └── pyannote_service.py # Wrapper pyannote.audio
│   └── watcher/
│       └── folder_watcher.py   # Monitor folderu (watchdog)
├── frontend/                   # Frontend React
│   ├── src/
│   │   ├── pages/              # Dashboard, Recordings, RecordingDetail, Search, Pipeline
│   │   ├── components/         # AudioPlayer, TranscriptViewer, SegmentTimeline...
│   │   ├── api/                # Klient API + typy TypeScript
│   │   └── hooks/              # useWebSocket
│   ├── package.json
│   └── vite.config.ts
├── alembic/                    # Migracje bazy danych
├── output/                     # Eksportowane transkrypcje
├── logs/                       # Logi aplikacji
├── Makefile                    # make install / dev / build / start
├── pyproject.toml              # Zależności Python
├── .env                        # Konfiguracja (nie commitować!)
└── transcriptions.db           # Baza SQLite (tworzona automatycznie)
```

## Baza danych

System używa SQLite z 4 tabelami:

- **recordings** — nagrania (filename, filepath, status, duration)
- **transcripts** — transkrypcje (full_text, language, model_used)
- **segments** — segmenty mowy (speaker_label, text, start_time, end_time, confidence)
- **speakers** — mówcy (label, role: agent/customer)

Migracje zarządzane przez Alembic: `alembic upgrade head`

## Makefile

```bash
make install   # Instalacja zależności (Python + Node)
make dev       # Tryb deweloperski (hot reload)
make build     # Build frontendu do produkcji
make start     # Start serwera produkcyjnego
make clean     # Czyszczenie artefaktów buildu
```

## Licencja

MIT
