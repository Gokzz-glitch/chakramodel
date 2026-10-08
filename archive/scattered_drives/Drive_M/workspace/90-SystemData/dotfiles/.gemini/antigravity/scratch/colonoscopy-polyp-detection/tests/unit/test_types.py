import pytest
import ast
import pathlib
import sys
import importlib

def test_frozen_dataclasses():
    from chakra.types import BBox, Detection, Track, PersistentTrack, FrameOutput
    import dataclasses
    
    assert dataclasses.is_dataclass(BBox)
    assert BBox.__dataclass_params__.frozen == True
    
    assert dataclasses.is_dataclass(Detection)
    assert Detection.__dataclass_params__.frozen == True
    
    assert dataclasses.is_dataclass(Track)
    assert Track.__dataclass_params__.frozen == True
    
    assert dataclasses.is_dataclass(PersistentTrack)
    assert PersistentTrack.__dataclass_params__.frozen == True
    
    assert dataclasses.is_dataclass(FrameOutput)
    assert FrameOutput.__dataclass_params__.frozen == True

    bbox = BBox(x=0.1, y=0.1, w=0.2, h=0.2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        bbox.x = 0.5
        
    detection = Detection(frame_idx=0, bbox=bbox, confidence=0.9, class_id=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        detection.confidence = 0.8

def test_import_boundaries():
    # chakra.types has zero chakra.* imports
    chakra_path = pathlib.Path(__file__).parent.parent.parent / "chakra"
    
    def get_imports(file_path):
        if not file_path.exists():
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    types_imports = get_imports(chakra_path / "types.py")
    for imp in types_imports:
        assert not imp.startswith("chakra"), f"chakra.types must not import {imp}"

    # chakra.protocols imports only chakra.types
    protocols_imports = get_imports(chakra_path / "protocols.py")
    for imp in protocols_imports:
        if imp.startswith("chakra"):
            assert imp == "chakra.types", f"chakra.protocols must only import chakra.types, got {imp}"

    # chakra.orchestrator has no direct implementation imports
    orchestrator_imports = get_imports(chakra_path / "orchestrator.py")
    # For now, let's just make sure it doesn't import implementation modules directly (assuming they're in chakra.detector etc)
    forbidden_modules = ["chakra.detector", "chakra.tracker", "chakra.persistence", "chakra.conformal", "chakra.renderer"]
    for imp in orchestrator_imports:
        assert not any(imp.startswith(fm) for fm in forbidden_modules), f"chakra.orchestrator must not import implementations directly, got {imp}"
