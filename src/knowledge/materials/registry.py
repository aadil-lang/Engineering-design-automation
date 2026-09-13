"""
Material Registry for Material Knowledge Base v1.
Loads, validates, and caches authoritative material records from data/materials.json.
Rejects malformed records through schema validation.
"""

import os
import json
from typing import Dict, List, Optional
from pydantic import ValidationError

from knowledge.materials.schema import MaterialRecord


DEFAULT_DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "materials.json"
)


class MaterialRegistry:
    """
    In-memory registry of validated MaterialRecords.
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or DEFAULT_DATA_PATH
        self._records_by_id: Dict[str, MaterialRecord] = {}
        self.load(self.data_path)

    def load(self, path: str) -> None:
        """
        Loads and validates all material records from a JSON file.
        Raises ValueError or ValidationError if file is missing, invalid JSON, or contains malformed records.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Material data file not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            try:
                raw_data = json.load(f)
            except json.JSONDecodeError as jde:
                raise ValueError(f"Malformed JSON in material data file '{path}': {str(jde)}")

        if not isinstance(raw_data, list):
            raise ValueError(f"Material data file must contain a top-level JSON array of records; got {type(raw_data).__name__}")

        records: Dict[str, MaterialRecord] = {}
        for idx, item in enumerate(raw_data):
            try:
                rec = MaterialRecord(**item)
                if rec.material_id in records:
                    raise ValueError(f"Duplicate material_id '{rec.material_id}' in '{path}' at index {idx}")
                records[rec.material_id] = rec
            except ValidationError as ve:
                raise ValueError(f"Malformed material record at index {idx} in '{path}': {ve}")

        self._records_by_id = records

    def get_all(self) -> List[MaterialRecord]:
        """Returns all registered material records."""
        return list(self._records_by_id.values())

    def get_by_id(self, material_id: str) -> Optional[MaterialRecord]:
        """Returns a record by exact material_id."""
        return self._records_by_id.get(material_id)


_DEFAULT_REGISTRY: Optional[MaterialRegistry] = None


def get_material_registry(data_path: Optional[str] = None) -> MaterialRegistry:
    """Singleton provider for MaterialRegistry."""
    global _DEFAULT_REGISTRY
    if data_path is not None:
        return MaterialRegistry(data_path=data_path)
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = MaterialRegistry()
    return _DEFAULT_REGISTRY
