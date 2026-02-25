import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4


class DataStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "index.csv"
        self.episodes_dir = self.base_dir / "episodes"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    def _ensure_index(self):
        if not self.index_path.exists():
            header = [
                "episode_id",
                "timestamp_local",
                "status",
                "grade",
                "temperature",
                "top_p",
                "min_p",
                "max_tokens",
                "seed",
                "mode",
            ]
            self.index_path.write_text(",".join(header) + os.linesep, encoding="utf-8")

    def _atomic_write_json(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)

    def _append_index_row(self, row: Dict[str, str]):
        self._ensure_index()
        with self.index_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    row.get("episode_id", ""),
                    row.get("timestamp_local", ""),
                    row.get("status", ""),
                    row.get("grade", ""),
                    row.get("temperature", ""),
                    row.get("top_p", ""),
                    row.get("min_p", ""),
                    row.get("max_tokens", ""),
                    row.get("seed", ""),
                    row.get("mode", ""),
                ]
            )

    def _update_index_row(self, episode_id: str, status: str, grade: Optional[int]):
        if not self.index_path.exists():
            return
        rows = []
        with self.index_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0] == "episode_id":
                    rows.append(row)
                    continue
                if row and row[0] == episode_id:
                    row[2] = status
                    row[3] = "" if grade is None else str(int(grade))
                rows.append(row)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=self.index_path.parent, newline="", encoding="utf-8") as tmp:
            writer = csv.writer(tmp)
            writer.writerows(rows)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.index_path)

    def create_episode(
        self,
        prompt_bytes: bytes,
        output_bytes: bytes,
        params: Dict,
        mode: str,
    ) -> str:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        short_id = uuid4().hex[:6]
        episode_id = f"{ts_str}_{short_id}"

        episode_dir = self.episodes_dir / date_str / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

        prompt_path = episode_dir / "prompt.mid"
        output_path = episode_dir / "output.mid"
        prompt_path.write_bytes(prompt_bytes)
        output_path.write_bytes(output_bytes)

        prompt_hash = hashlib.sha256(prompt_bytes).hexdigest()
        output_hash = hashlib.sha256(output_bytes).hexdigest()

        meta = {
            "episode_id": episode_id,
            "timestamp_local": now.isoformat(),
            "status": "draft",
            "grade": None,
            "mode": mode,
            "temperature": params.get("temperature"),
            "top_p": params.get("top_p"),
            "min_p": params.get("min_p"),
            "max_tokens": params.get("max_tokens"),
            "seed": params.get("seed"),
            "hashes": {
                "prompt_mid_sha256": prompt_hash,
                "output_mid_sha256": output_hash,
            },
        }
        self._atomic_write_json(episode_dir / "meta.json", meta)

        self._append_index_row(
            {
                "episode_id": episode_id,
                "timestamp_local": meta["timestamp_local"],
                "status": "draft",
                "grade": "",
                "temperature": params.get("temperature"),
                "top_p": params.get("top_p"),
                "min_p": params.get("min_p"),
                "max_tokens": params.get("max_tokens"),
                "seed": params.get("seed"),
                "mode": mode,
            }
        )

        return episode_id

    def finalize_episode(self, episode_id: str, grade: int):
        # Find meta.json
        meta_path = None
        for candidate in self.episodes_dir.rglob("meta.json"):
            try:
                with candidate.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("episode_id") == episode_id:
                    meta_path = candidate
                    meta = data
                    break
            except Exception:
                continue
        if not meta_path:
            return

        meta["status"] = "final"
        meta["grade"] = int(grade)
        self._atomic_write_json(meta_path, meta)
        self._update_index_row(episode_id, "final", int(grade))
