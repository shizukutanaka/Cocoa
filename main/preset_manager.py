import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from logging_manager import Logger
except ImportError:
    Logger = logging.Logger
from collections import defaultdict


class PresetError(Exception):
    """プリセット操作に関するエラー。"""


class PresetManager:
    """Manage and manipulate presets"""

    def __init__(self, logger: Logger, preset_dir: str = "presets"):
        """Initialize preset manager"""
        self.logger = logger
        self.preset_dir = Path(preset_dir)
        self.presets: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, Set[str]] = defaultdict(set)  # 検索インデックス
        self._tags_index: Dict[str, List[str]] = defaultdict(list)  # タグベースのインデックス

    def load_presets(self) -> None:
        """Load all available presets"""
        try:
            if not self.preset_dir.exists():
                self.logger.warning(f"Preset directory not found: {self.preset_dir}")
                return

            self.presets.clear()
            self._index.clear()
            self._tags_index.clear()

            for preset_file in self.preset_dir.glob("*.json"):
                preset_name = preset_file.stem
                preset_data = self._load_preset(preset_file)
                self.presets[preset_name] = preset_data
                self._update_index(preset_name, preset_data)

            self.logger.info(f"Loaded {len(self.presets)} presets")

        except Exception as e:
            self.logger.error(f"Error loading presets: {str(e)}")
            raise PresetError(f"Failed to load presets: {str(e)}") from e

    def _load_preset(self, preset_file: Path) -> Dict[str, Any]:
        """Load a single preset"""
        try:
            with open(preset_file, encoding='utf-8') as f:
                preset_data = json.load(f)

            # Validate preset data
            self._validate_preset(preset_data)
            return preset_data

        except Exception as e:
            self.logger.error(f"Error loading preset {preset_file}: {str(e)}")
            raise PresetError(f"Failed to load preset {preset_file}: {str(e)}") from e

    def _update_index(self, preset_name: str, preset_data: Dict[str, Any]) -> None:
        """プリセットのインデックスを更新"""
        # パラメータ名によるインデックス
        for param_name in preset_data.get('parameters', {}):
            self._index[param_name].add(preset_name)

        # タグによるインデックス
        tags = preset_data.get('tags', [])
        for tag in tags:
            if preset_name not in self._tags_index[tag]:
                self._tags_index[tag].append(preset_name)

    def search_presets(self, query: str) -> List[str]:
        """プリセットを検索"""
        if not query:
            return list(self.presets.keys())

        q = query.lower()
        matching_presets = set()

        # パラメータ名による検索
        for param_name in self._index:
            if q in param_name.lower():
                matching_presets.update(self._index[param_name])

        # タグによる検索 (_tags_index was built but previously not queried)
        for tag_name in self._tags_index:
            if q in tag_name.lower():
                matching_presets.update(self._tags_index[tag_name])

        # プリセット名による検索
        for preset_name in self.presets:
            if q in preset_name.lower():
                matching_presets.add(preset_name)

        return list(matching_presets)

    def batch_update_presets(self, updates: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """複数のプリセットをバッチ更新"""
        results = {}
        for preset_name, new_data in updates.items():
            try:
                self.save_preset(preset_name, new_data)
                results[preset_name] = True
            except Exception as e:
                self.logger.error(f"Failed to update preset {preset_name}: {e}")
                results[preset_name] = False
        return results

    def batch_delete_presets(self, preset_names: List[str]) -> Dict[str, bool]:
        """複数のプリセットをバッチ削除"""
        results = {}
        for preset_name in preset_names:
            try:
                self.delete_preset(preset_name)
                results[preset_name] = True
            except Exception as e:
                self.logger.error(f"Failed to delete preset {preset_name}: {e}")
                results[preset_name] = False
        return results

    def _safe_preset_path(self, preset_name: str) -> Path:
        """Return the resolved Path for preset_name, raising PresetError if it
        would escape preset_dir (path-traversal guard)."""
        candidate = (self.preset_dir / f"{preset_name}.json").resolve()
        try:
            candidate.relative_to(self.preset_dir.resolve())
        except ValueError:
            raise PresetError(f"無効なプリセット名です: {preset_name}")
        return candidate

    def save_preset(self, preset_name: str, preset_data: Dict[str, Any]) -> None:
        """Save a new or updated preset"""
        try:
            # Validate data
            self._validate_preset(preset_data)

            # Guard against path traversal
            preset_file = self._safe_preset_path(preset_name)

            # Create preset directory if needed
            self.preset_dir.mkdir(parents=True, exist_ok=True)

            # Save preset
            with open(preset_file, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, ensure_ascii=False, indent=2)

            # Remove stale index entries before adding new ones
            if preset_name in self.presets:
                self._remove_from_index(preset_name, self.presets[preset_name])

            # Update cache and index
            self.presets[preset_name] = preset_data
            self._update_index(preset_name, preset_data)

            self.logger.info(f"Saved preset: {preset_name}")

        except Exception as e:
            self.logger.error(f"Error saving preset {preset_name}: {str(e)}")
            raise PresetError(f"Failed to save preset {preset_name}: {str(e)}") from e

    def delete_preset(self, preset_name: str) -> None:
        """Delete a preset"""
        try:
            preset_file = self._safe_preset_path(preset_name)
            if preset_file.exists():
                preset_file.unlink()
                self.logger.info(f"Deleted preset: {preset_name}")

                # Remove from cache and index
                if preset_name in self.presets:
                    preset_data = self.presets[preset_name]
                    del self.presets[preset_name]

                    # インデックスから削除
                    self._remove_from_index(preset_name, preset_data)

            else:
                raise PresetError(f"Preset not found: {preset_name}")

        except Exception as e:
            self.logger.error(f"Error deleting preset {preset_name}: {str(e)}")
            raise PresetError(f"Failed to delete preset {preset_name}: {str(e)}") from e

    def _validate_preset(self, preset_data: Dict[str, Any]) -> None:
        """Validate preset data structure"""
        if not isinstance(preset_data, dict):
            raise PresetError("Preset data must be a dictionary")

    def _remove_from_index(self, preset_name: str, preset_data: Dict[str, Any]) -> None:
        """プリセットをインデックスから削除"""
        # パラメータ名によるインデックスから削除
        for param_name in preset_data.get('parameters', {}):
            if preset_name in self._index[param_name]:
                self._index[param_name].remove(preset_name)
                if not self._index[param_name]:
                    del self._index[param_name]

        # タグによるインデックスから削除
        tags = preset_data.get('tags', [])
        for tag in tags:
            if preset_name in self._tags_index[tag]:
                self._tags_index[tag].remove(preset_name)
                if not self._tags_index[tag]:
                    del self._tags_index[tag]

    def get_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific preset"""
        if preset_name not in self.presets:
            self.logger.warning(f"Preset not found in cache: {preset_name}")
            return None

        return self.presets[preset_name].copy()

    def get_all_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get all loaded presets"""
        return {k: v.copy() for k, v in self.presets.items()}

    def compare_presets(self, preset1: str, preset2: str) -> Dict[str, Any]:
        """Compare two presets"""
        try:
            p1 = self.get_preset(preset1)
            p2 = self.get_preset(preset2)

            if not p1 or not p2:
                raise PresetError("One or both presets not found")

            differences = {}
            all_keys = set(p1.keys()).union(p2.keys())

            for key in all_keys:
                if p1.get(key) != p2.get(key):
                    differences[key] = {
                        'preset1': p1.get(key),
                        'preset2': p2.get(key)
                    }

            self.logger.info(f"Found {len(differences)} differences between presets")
            return {
                'preset1': preset1,
                'preset2': preset2,
                'differences': differences
            }

        except Exception as e:
            self.logger.error(f"Error comparing presets: {str(e)}")
            raise PresetError(f"Failed to compare presets: {str(e)}") from e

    def merge_presets(self, base_preset: str, update_preset: str) -> Dict[str, Any]:
        """Merge two presets, with update_preset taking precedence"""
        try:
            base = self.get_preset(base_preset)
            update = self.get_preset(update_preset)

            if not base or not update:
                raise PresetError("One or both presets not found")

            # Merge parameters
            merged = base.copy()
            for key, value in update.items():
                merged[key] = value

            self.logger.info(f"Merged presets: {base_preset} and {update_preset}")
            return merged

        except Exception as e:
            self.logger.error(f"Error merging presets: {str(e)}")
            raise PresetError(f"Failed to merge presets: {str(e)}") from e
