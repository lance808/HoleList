import json
import os
import uuid
from datetime import datetime


class DataManager:
    """数据管理器，负责所有 JSON 文件的读写"""

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir
        self.settings_file = os.path.join(base_dir, "data.txt")
        self.holes_file = os.path.join(base_dir, "Hole.txt")
        self.memos_file = os.path.join(base_dir, "list.txt")
        self._ensure_files()

    def _ensure_files(self):
        defaults = {
            self.settings_file: {
                "theme": "light",
                "colors": {
                    "bg": "#FFFFFF",
                    "text": "#333333",
                    "border": "#CCCCCC",
                },
                "dark_colors": {
                    "bg": "#1E1E1E",
                    "text": "#D4D4D4",
                    "border": "#444444",
                },
                "transparency": 60,
                "auto_start": False,
                "default_tab": 0,
                "default_pinned": False,
                "font_size": 12,
                "window": {"x": 100, "y": 100, "width": 800, "height": 600},
            },
            self.holes_file: {"holes": []},
            self.memos_file: {"memos": []},
        }
        for filepath, default_data in defaults.items():
            if not os.path.exists(filepath):
                self._save_json(filepath, default_data)

    def _load_json(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def _save_json(self, filepath, data):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ========== 设置 ==========

    def load_settings(self):
        return self._load_json(self.settings_file)

    def save_settings(self, settings):
        self._save_json(self.settings_file, settings)

    # ========== 坑 ==========

    def load_holes(self):
        data = self._load_json(self.holes_file)
        return data.get("holes", []) if data else []

    def save_holes(self, holes):
        self._save_json(self.holes_file, {"holes": holes})

    def add_hole(self, title, description=""):
        holes = self.load_holes()
        digging = [h for h in holes if h["status"] == "digging"]
        max_order = max([h["order"] for h in digging], default=-1)
        hole = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "description": description,
            "created_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "digging",
            "order": max_order + 1,
        }
        holes.append(hole)
        self.save_holes(holes)
        return hole

    def update_hole(self, hole_id, **kwargs):
        holes = self.load_holes()
        for hole in holes:
            if hole["id"] == hole_id:
                hole.update(kwargs)
                break
        self.save_holes(holes)

    def delete_hole(self, hole_id):
        holes = self.load_holes()
        holes = [h for h in holes if h["id"] != hole_id]
        self.save_holes(holes)

    def move_hole(self, hole_id, new_status):
        holes = self.load_holes()
        for hole in holes:
            if hole["id"] == hole_id:
                hole["status"] = new_status
                same_status = [h for h in holes if h["status"] == new_status]
                max_order = max([h["order"] for h in same_status], default=-1)
                hole["order"] = max_order + 1
                break
        self.save_holes(holes)

    def reorder_holes(self, status, hole_ids):
        holes = self.load_holes()
        for i, hid in enumerate(hole_ids):
            for hole in holes:
                if hole["id"] == hid and hole["status"] == status:
                    hole["order"] = i
                    break
        self.save_holes(holes)

    # ========== 备忘录 ==========

    def load_memos(self):
        data = self._load_json(self.memos_file)
        return data.get("memos", []) if data else []

    def save_memos(self, memos):
        self._save_json(self.memos_file, {"memos": memos})

    def add_memo(self, title, content=""):
        memos = self.load_memos()
        max_order = max([m["order"] for m in memos], default=-1)
        memo = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "content": content,
            "created_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "order": max_order + 1,
            "completed": False,
        }
        memos.append(memo)
        self.save_memos(memos)
        return memo

    def update_memo(self, memo_id, **kwargs):
        memos = self.load_memos()
        for memo in memos:
            if memo["id"] == memo_id:
                memo.update(kwargs)
                break
        self.save_memos(memos)

    def delete_memo(self, memo_id):
        memos = self.load_memos()
        memos = [m for m in memos if m["id"] != memo_id]
        self.save_memos(memos)

    def reorder_memos(self, memo_ids):
        memos = self.load_memos()
        for i, mid in enumerate(memo_ids):
            for memo in memos:
                if memo["id"] == mid:
                    memo["order"] = i
                    break
        self.save_memos(memos)