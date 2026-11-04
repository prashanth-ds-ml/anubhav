"""Deploy the app to a Hugging Face Docker Space: only git-tracked files the Dockerfile needs, a Space README header,
and the model keys as Space secrets (never in the image): the Meta key for Muse Spark 1.3, and the Baseten key for Muse
Spark Open, kept for judges (D-048). Both run under the same live caps.

    set -a; . ./.env; set +a
    uvx --from huggingface_hub python scripts/deploy_space.py [--space KPrashanth/anubhav] [--no-secret]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
PATHS = ["Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock", "README.md", "LICENSE", "src", "configs", "contracts",
         "demo", "web", "artifacts", "archive/prototype_experiments/artifacts/baseline"]
SKIP = ("web/e2e/", "web/readme-assets/", "web/tools/", "web/scripts/")
HEADER = """---
title: Anubhav
emoji: 🚚
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Self-improving agents that learn a fleet's unwritten rules
---

"""


def files():
    out = subprocess.run(["git", "ls-files", *PATHS], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    return [f for f in out if f and not f.startswith(SKIP)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", default="KPrashanth/anubhav")
    ap.add_argument("--no-secret", action="store_true")
    a = ap.parse_args()
    keys = [os.environ.get(k, "") for k in ("meta_api", "baseten_api_key", "HF_TOKEN")]
    api = HfApi(token=os.environ["HF_TOKEN"])
    with tempfile.TemporaryDirectory() as tmp:
        for f in files():
            dst = Path(tmp, f)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / f, dst)
            if any(len(k) > 8 and k in dst.read_text(encoding="utf-8", errors="ignore") for k in keys):
                sys.exit(f"refusing: a key value is in {f}")
        readme = Path(tmp, "README.md")
        readme.write_text(HEADER + readme.read_text(encoding="utf-8"), encoding="utf-8")
        api.create_repo(a.space, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
        if not a.no_secret:
            for k in ("meta_api", "baseten_api_key"):
                if os.environ.get(k):
                    api.add_space_secret(a.space, k, os.environ[k])
        api.upload_folder(repo_id=a.space, repo_type="space", folder_path=tmp, delete_patterns=["*"],
                          commit_message="Deploy from github.com/prashanth-ds-ml/anubhav")
    print("https://huggingface.co/spaces/" + a.space)


if __name__ == "__main__":
    main()
