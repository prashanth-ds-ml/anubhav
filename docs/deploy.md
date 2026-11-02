# Deploying the demo (Streamlit Community Cloud)

The app runs on a fresh checkout with no data and no keys:
- the demo world is generated from its seed on first start (about 20 seconds locally, up to a minute on the host; identical to the local one: same snapshot hashes);
- **Replay (free)** uses saved real runs from `demo/replay_runs.jsonl`;
- **Demo controls → Load EXP-008 lessons** loads `demo/exp008_lessons.json`;
- **Tool skills** shows the EXP-010 practice results from `demo/practice.json`.

Live mode and voice need keys. Without them, the app says so and stays on replay.

## Steps
1. Go to share.streamlit.io and sign in with the **prashanth-ds-ml** GitHub account.
2. Click **Create app**, choose repo `prashanth-ds-ml/anubhav`, branch `main` and main file `streamlit_app.py`.
3. Under **Advanced settings**, pick Python 3.12.
4. In **Secrets**, always set public mode; add the keys only if you want live runs:
   ```toml
   ANUBHAV_PUBLIC = "1"      # each visitor gets their own drafts and lessons (starting from EXP-008)
   meta_api = "..."          # optional: Muse Spark 1.3 + Muse Voice Transcribe
   baseten_api_key = "..."   # optional: Muse Spark Open
   ```
   Top-level secrets reach the app as environment variables.
5. Click **Deploy**.

## Spend control
- Each browser session gets `LIVE_RUNS_PER_SESSION` live runs (8, in `src/anubhav/service/session.py`), at about $0.05 each.
- The whole app gets `LIVE_CALLS_PER_DAY` live calls (60), counted in a file, so reloading the page doesn't reset it.
- Every live button (agent, miner, practice, tuning, voice) goes through the same check; without keys they are disabled and say why.
- Replay is the default and costs nothing.
- `LIVE_CALLS_PER_DAY_BY_MODEL` also limits Muse Spark Open to 30 live runs a day, so Baseten's smaller credit lasts (D-048).
- **For judging, deploy with both keys (owner, Nov 1)** so judges can pick either model. Set spend alerts on both billing pages first.

## Refreshing the demo bundle
After new real runs locally: `uv run python scripts/export_demo.py`, then check the bundle for secrets and commit `demo/`.

## FastAPI on a Hugging Face Docker Space (D-044)
The Streamlit link stays the hosted demo until the web app is on a Space. The API image, with the web app inside it, is built and checked locally: the last check (Nov 2, commit `2393361`) ran it with no keys as user `anubhav` and passed health, session, `/api/proof`, the registry, the lesson evidence and run-steps routes, every main tab and S1 end to end.

1. Check it locally: `docker build -t anubhav-api .` then `docker run --rm -p 7860:7860 anubhav-api`, and open http://localhost:7860/ (the web app) and http://localhost:7860/docs. The build has a Node stage that runs `npm ci` and `npm run build` in `web/` and copies `web/dist` into the image, so the API serves the web app at `/`. The first build took about 7 minutes and the image is about 2.2 GB. Checked on Nov 1 with no keys: `/api/health` answers after about 30 s, `/api/session` shows replay mode with live and voice off, the page and its script load, a saved request plays, and the app runs as a non-root user.
2. Create a new Space with the **Docker** SDK and **Public** visibility. Its README needs this front matter (don't add it to this repo's README, which GitHub shows):
   ```yaml
   ---
   title: Anubhav
   sdk: docker
   app_port: 7860
   ---
   ```
3. Push this repo's files to the Space. For replay-only hosting, add no secrets: live mode stays off and costs $0.
4. For live mode (scenarios S4 and S5), add only `meta_api` as a Space **secret**, never in a file: live runs use Muse Spark 1.3 on Meta's API (D-050). Leave `baseten_api_key` unset. Caps apply: 8 runs per session, 60 per day.
5. Space storage resets on a restart unless persistent storage is attached. The demo world is in the image, so only visitors' drafts and saved live runs are lost. A visitor's drafts and lessons are removed after 2 days without a change (checked at start and at most hourly); their run records stay.
6. Check in an incognito window: `/api/health`, `/docs`, and a replay through `/api/chat` and `/api/chat/stream`.

