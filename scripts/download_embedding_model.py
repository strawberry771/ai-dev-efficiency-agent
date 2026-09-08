#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download the local Chinese embedding model (BGE-small-zh-v1.5).

Target directory: models/bge-small-zh-v1.5/

Method: git clone from ModelScope's official model-git endpoint.

Why not ``from modelscope import snapshot_download``? The ModelScope SDK's own
source tree exceeds Windows MAX_PATH when installed under this (already long)
project path, so the SDK cannot be installed here. git clone is the
ModelScope-supported equivalent, needs no extra SDK, and produces a plain local
directory of model files that sentence-transformers can load offline.

Idempotent: skips the download when the core model files are already present.
"""
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
MODEL_ID = "AI-ModelScope/bge-small-zh-v1.5"
DEST = os.path.join(HERE, "models", "bge-small-zh-v1.5")

# Files that must exist for the model to be usable by sentence-transformers.
CORE_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "special_tokens_map.json",
    "sentence_bert_config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "1_Pooling/config.json",
)


def is_complete(dest: str) -> bool:
    return all(os.path.isfile(os.path.join(dest, f)) for f in CORE_FILES)


def main() -> None:
    if is_complete(DEST):
        print(f"Model already present at {DEST}; nothing to do.")
        return

    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    url = f"https://www.modelscope.cn/{MODEL_ID}.git"

    if os.path.isdir(DEST):
        shutil.rmtree(DEST)

    subprocess.check_call(["git", "clone", "--depth", "1", url, DEST])

    # Drop git metadata so only the model files remain.
    gitdir = os.path.join(DEST, ".git")
    if os.path.isdir(gitdir):
        shutil.rmtree(gitdir)

    if not is_complete(DEST):
        raise SystemExit(
            "Download incomplete: core model files missing. Check network and retry."
        )

    print(f"OK: embedding model ready at {DEST}")


if __name__ == "__main__":
    main()
