"""Download competition data from Kaggle.

Requires the Kaggle CLI to be configured (`~/.kaggle/kaggle.json` with API
credentials, or KAGGLE_USERNAME / KAGGLE_KEY env vars).

You must also accept each competition's rules on the Kaggle website before
the first download — otherwise the API returns a 403.

The bundled `CASE_SHORTHANDS` is just a convenience map for the three
demonstration cases in this case description. The system is not limited
to them: `download_kaggle_competition(slug, out)` works for any
competition slug.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


# Convenience shorthands for the three demonstration cases.
# To add a new competition, just write configs/<name>.yaml and call
# `python -m maads data download --competition <slug>` directly.
CASE_SHORTHANDS = {
    "titanic": "titanic",
    "house_prices": "house-prices-advanced-regression-techniques",
    "disaster_tweets": "nlp-getting-started",
}


def download_kaggle_competition(slug: str, out_dir: Path) -> Path:
    """Download files for any Kaggle competition into out_dir.

    Args:
        slug: the competition slug as it appears in the Kaggle URL
              (e.g. 'titanic', 'spaceship-titanic',
              'tabular-playground-series-jan-2026').
        out_dir: directory to write into. Created if missing.

    Returns:
        The path to out_dir.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "kaggle", "competitions", "download",
        "-c", slug,
        "-p", str(out_dir),
    ]
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Kaggle download failed for '{slug}'. Have you accepted the "
            "competition rules on Kaggle's website and configured "
            "`~/.kaggle/kaggle.json`?\n"
            f"stderr: {proc.stderr}"
        )

    # Unzip the downloaded archive(s).
    for zipfile in out_dir.glob("*.zip"):
        subprocess.run(["unzip", "-o", str(zipfile), "-d", str(out_dir)],
                       check=True, capture_output=True)
        zipfile.unlink()

    print(f"Downloaded {slug} to {out_dir}")
    return out_dir


def download_case_data(case: str, data_dir: Path | None = None) -> Path:
    """Convenience wrapper for the three demonstration cases.

    For arbitrary Kaggle competitions, call `download_kaggle_competition`
    directly.
    """
    if case not in CASE_SHORTHANDS:
        raise ValueError(
            f"Unknown case shorthand: {case!r}. "
            f"Known: {list(CASE_SHORTHANDS)}. "
            "For arbitrary competitions, use "
            "`download_kaggle_competition(slug, out_dir)`."
        )
    slug = CASE_SHORTHANDS[case]
    base = Path(data_dir) if data_dir is not None else Path("data")
    return download_kaggle_competition(slug, base / case)
