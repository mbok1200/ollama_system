import os
import json
from datetime import datetime, timedelta


class SessionManager:
    def __init__(self, base_path="sessions", refresh_hours=24):
        self.base_path = base_path
        self.refresh_delta = timedelta(hours=refresh_hours)

        os.makedirs(base_path, exist_ok=True)

    def _state_path(self, account_id):
        return os.path.join(self.base_path, f"{account_id}.json")

    def _meta_path(self, account_id):
        return os.path.join(self.base_path, f"{account_id}.meta.json")

    def exists(self, account_id):
        return os.path.exists(self._state_path(account_id))

    def load(self, account_id):
        return self._state_path(account_id) if self.exists(account_id) else None

    def save(self, context, account_id):
        # зберігаємо cookies/state
        context.storage_state(path=self._state_path(account_id))

        # оновлюємо метадані
        meta = {
            "last_refresh": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat()
        }

        with open(self._meta_path(account_id), "w") as f:
            json.dump(meta, f)
        print(f"Session for {self._meta_path(account_id)} saved.")

    def mark_used(self, account_id):
        meta = self._read_meta(account_id)
        if meta:
            meta["last_used"] = datetime.utcnow().isoformat()
            self._write_meta(account_id, meta)

    def needs_refresh(self, account_id):
        meta = self._read_meta(account_id)
        if not meta:
            return True

        last_refresh = datetime.fromisoformat(meta["last_refresh"])
        return datetime.utcnow() - last_refresh > self.refresh_delta

    def _read_meta(self, account_id):
        path = self._meta_path(account_id)
        if not os.path.exists(path):
            return None

        with open(path, "r") as f:
            return json.load(f)

    def _write_meta(self, account_id, data):
        with open(self._meta_path(account_id), "w") as f:
            json.dump(data, f)