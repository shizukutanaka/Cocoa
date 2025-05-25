import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from .error_handling import PresetError
from .logging_manager import Logger

class PresetManager:
    """Manage and manipulate presets"""
    
    def __init__(self, logger: Logger, preset_dir: str = "presets"):
        """Initialize preset manager"""
        self.logger = logger
        self.preset_dir = Path(preset_dir)
        self.presets: Dict[str, Dict[str, Any]] = {}
        
    def load_presets(self) -> None:
        """Load all available presets"""
        try:
            if not self.preset_dir.exists():
                self.logger.warning(f"Preset directory not found: {self.preset_dir}")
                return
                
            self.presets.clear()
            
            for preset_file in self.preset_dir.glob("*.json"):
                preset_name = preset_file.stem
                self.presets[preset_name] = self._load_preset(preset_file)
                
            self.logger.info(f"Loaded {len(self.presets)} presets")
            
        except Exception as e:
            self.logger.error(f"Error loading presets: {str(e)}")
            raise PresetError(f"Failed to load presets: {str(e)}")
    
    def _load_preset(self, preset_file: Path) -> Dict[str, Any]:
        """Load a single preset"""
        try:
            with open(preset_file, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
                
            # Validate preset data
            self._validate_preset(preset_data)
            return preset_data
            
        except Exception as e:
            self.logger.error(f"Error loading preset {preset_file}: {str(e)}")
            raise PresetError(f"Failed to load preset {preset_file}: {str(e)}")
    
    def _validate_preset(self, preset_data: Dict[str, Any]) -> None:
        """Validate preset data"""
        required_keys = ['name', 'version', 'parameters']
        
        for key in required_keys:
            if key not in preset_data:
                raise PresetError(f"Missing required key in preset: {key}")
                
        if not isinstance(preset_data['parameters'], dict):
            raise PresetError("Parameters must be a dictionary")
    
    def save_preset(self, preset_name: str, preset_data: Dict[str, Any]) -> None:
        """Save a new or updated preset"""
        try:
            # Validate data
            self._validate_preset(preset_data)
            
            # Create preset directory if needed
            self.preset_dir.mkdir(parents=True, exist_ok=True)
            
            # Save preset
            preset_file = self.preset_dir / f"{preset_name}.json"
            with open(preset_file, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Saved preset: {preset_name}")
            
        except Exception as e:
            self.logger.error(f"Error saving preset {preset_name}: {str(e)}")
            raise PresetError(f"Failed to save preset {preset_name}: {str(e)}")
    
    def delete_preset(self, preset_name: str) -> None:
        """Delete a preset"""
        try:
            preset_file = self.preset_dir / f"{preset_name}.json"
            if preset_file.exists():
                preset_file.unlink()
                self.logger.info(f"Deleted preset: {preset_name}")
                
                # Remove from cache
                if preset_name in self.presets:
                    del self.presets[preset_name]
                    
            else:
                raise PresetError(f"Preset not found: {preset_name}")
                
        except Exception as e:
            self.logger.error(f"Error deleting preset {preset_name}: {str(e)}")
            raise PresetError(f"Failed to delete preset {preset_name}: {str(e)}")
    
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
            raise PresetError(f"Failed to compare presets: {str(e)}")
    
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
            raise PresetError(f"Failed to merge presets: {str(e)}")
