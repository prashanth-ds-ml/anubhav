# Deploying the demo (Streamlit Community Cloud)

The app runs on a fresh checkout with no data and no keys:
- the demo world is generated from its seed on first start (a few seconds, identical to the local one: same snapshot hashes);
- **Replay (free)** uses saved real runs from `demo/replay_runs.jsonl`;
- **Demo controls → Load EXP-008 lessons** loads `demo/exp008_lessons.json`;
- **Tool skills** shows the EXP-010 practice results from `demo/practice.json`.

Live mode and voice need keys. Without them, the app says so and stays on replay.

## Steps
1. Go to share.streamlit.io and sign in with the **prashanth-ds-ml** GitHub account.
2. Click **Create app**, choose repo `prashanth-ds-ml/anubhav`, branch `main` and main file `streamlit_app.py`.
3. Under **Advanced settings**, pick Python 3.12.
4. Optional: to allow live runs, paste these into **Secrets**:
   ```toml
   meta_api = "..."          # Muse Spark 1.3 + Muse Voice Transcribe
   baseten_api_key = "..."   # Muse Spark Open
   ```
   Top-level secrets reach the app as environment variables.
5. Click **Deploy**.

## Spend control
- Each browser session gets `LIVE_RUNS_PER_SESSION` live runs (8, in `src/anubhav/ui/core.py`), at about $0.05 each.
- Replay is the default and costs nothing.
- For judging, the safest choice is to deploy **without** secrets (replay only) and show live runs in the video.

## Refreshing the demo bundle
After new real runs locally: `uv run python scripts/export_demo.py`, then check the bundle for secrets and commit `demo/`.
