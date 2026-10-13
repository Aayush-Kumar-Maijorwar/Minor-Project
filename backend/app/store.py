"""
Flat-file store for patients/analyses/flags (backend/data/store.json, gitignored - it's
runtime state, not a fixture). Atomic writes: write to a temp file in the same directory,
then os.replace() so a crash mid-write never leaves a half-written store.json.
"""
import json
import os
import tempfile
from pathlib import Path
from threading import Lock

_EMPTY = {"patients": [], "analyses": [], "flags": []}


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self.path.exists():
            self._write(dict(_EMPTY))

    def _read(self) -> dict:
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(_EMPTY)

    def _write(self, data: dict):
        fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-store-")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    # ---- patients -----------------------------------------------------
    def list_patients(self) -> list[dict]:
        with self._lock:
            return list(self._read()["patients"])

    def get_patient(self, patient_id: str) -> dict | None:
        with self._lock:
            return next((p for p in self._read()["patients"] if p["id"] == patient_id), None)

    def add_patient(self, patient: dict) -> dict:
        with self._lock:
            data = self._read()
            data["patients"].append(patient)
            self._write(data)
            return patient

    def update_patient(self, patient_id: str, **fields):
        with self._lock:
            data = self._read()
            for p in data["patients"]:
                if p["id"] == patient_id:
                    p.update(fields)
                    break
            self._write(data)

    # ---- analyses -------------------------------------------------------
    def add_analysis(self, analysis: dict) -> dict:
        with self._lock:
            data = self._read()
            data["analyses"].append(analysis)
            data["flags"].extend(analysis.get("flags", []))
            self._write(data)
            return analysis

    def list_analyses(self) -> list[dict]:
        with self._lock:
            return list(self._read()["analyses"])

    def get_analysis(self, analysis_id: str) -> dict | None:
        with self._lock:
            return next((a for a in self._read()["analyses"] if a["id"] == analysis_id), None)

    def update_analysis(self, analysis_id: str, **fields) -> dict | None:
        with self._lock:
            data = self._read()
            target = None
            for a in data["analyses"]:
                if a["id"] == analysis_id:
                    a.update(fields)
                    target = a
                    break
            self._write(data)
            return target

    # ---- flags ------------------------------------------------------------
    def list_flags(self) -> list[dict]:
        with self._lock:
            return list(self._read()["flags"])

    def update_flag(self, flag_id: str, **fields) -> dict | None:
        with self._lock:
            data = self._read()
            target = None
            for f in data["flags"]:
                if f["id"] == flag_id:
                    f.update(fields)
                    target = f
                    break
            self._write(data)
            return target
