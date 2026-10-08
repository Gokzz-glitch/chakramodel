"""Tests for validate_excalidraw.py"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_excalidraw import validate


def _write_temp(data):
    """Write data to a temp .excalidraw file and return the path."""
    with tempfile.NamedTemporaryFile(suffix=".excalidraw", delete=False, mode="w") as f:
        json.dump(data, f)
        return f.name


def _valid_doc():
    """Return a minimal valid .excalidraw document."""
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "test",
        "elements": [
            {
                "id": "rect1",
                "type": "rectangle",
                "x": 100,
                "y": 100,
                "width": 200,
                "height": 80,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "groupIds": [],
                "frameId": None,
                "roundness": {"type": 3},
                "seed": 12345,
                "version": 1,
                "versionNonce": 67890,
                "isDeleted": False,
                "boundElements": [],
                "updated": 1700000000000,
                "link": None,
                "locked": False,
            }
        ],
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }


class TestValidDoc:
    def test_valid_passes(self):
        path = _write_temp(_valid_doc())
        result = validate(path)
        assert result["status"] == "pass"
        assert result["summary"]["total"] == 0
        Path(path).unlink()


class TestInvalidJson:
    def test_bad_json(self):
        with tempfile.NamedTemporaryFile(suffix=".excalidraw", delete=False, mode="w") as f:
            f.write("{invalid json")
            path = f.name
        result = validate(path)
        assert any(f["severity"] == "critical" for f in result)
        Path(path).unlink()

    def test_file_not_found(self):
        result = validate("/nonexistent/file.excalidraw")
        assert any(f["severity"] == "critical" for f in result)


class TestStructure:
    def test_wrong_type(self):
        doc = _valid_doc()
        doc["type"] = "not-excalidraw"
        path = _write_temp(doc)
        result = validate(path)
        assert result["status"] == "fail"
        assert any("type" in f["issue"].lower() for f in result["findings"])
        Path(path).unlink()

    def test_missing_elements(self):
        doc = _valid_doc()
        del doc["elements"]
        path = _write_temp(doc)
        result = validate(path)
        assert result["status"] == "fail"
        Path(path).unlink()

    def test_elements_not_array(self):
        doc = _valid_doc()
        doc["elements"] = "not an array"
        path = _write_temp(doc)
        result = validate(path)
        assert result["status"] == "fail"
        Path(path).unlink()


class TestElements:
    def test_missing_id(self):
        doc = _valid_doc()
        del doc["elements"][0]["id"]
        path = _write_temp(doc)
        result = validate(path)
        assert any(f["severity"] == "critical" and "id" in f["issue"] for f in result["findings"])
        Path(path).unlink()

    def test_duplicate_id(self):
        doc = _valid_doc()
        elem2 = dict(doc["elements"][0])  # same ID
        doc["elements"].append(elem2)
        path = _write_temp(doc)
        result = validate(path)
        assert any("uplicate" in f["issue"] for f in result["findings"])
        Path(path).unlink()

    def test_invalid_type(self):
        doc = _valid_doc()
        doc["elements"][0]["type"] = "banana"
        path = _write_temp(doc)
        result = validate(path)
        assert any("nvalid element type" in f["issue"] for f in result["findings"])
        Path(path).unlink()

    def test_missing_position(self):
        doc = _valid_doc()
        del doc["elements"][0]["x"]
        path = _write_temp(doc)
        result = validate(path)
        assert any("'x'" in f["issue"] for f in result["findings"])
        Path(path).unlink()


class TestTextElements:
    def test_text_missing_text_field(self):
        doc = _valid_doc()
        doc["elements"][0]["type"] = "text"
        # No 'text' field
        path = _write_temp(doc)
        result = validate(path)
        assert any("text" in f["issue"].lower() and f["severity"] == "high" for f in result["findings"])
        Path(path).unlink()

    def test_invalid_text_align(self):
        doc = _valid_doc()
        doc["elements"][0]["type"] = "text"
        doc["elements"][0]["text"] = "Hello"
        doc["elements"][0]["textAlign"] = "justify"
        path = _write_temp(doc)
        result = validate(path)
        assert any("textAlign" in f["issue"] for f in result["findings"])
        Path(path).unlink()


class TestLinearElements:
    def test_arrow_missing_points(self):
        doc = _valid_doc()
        doc["elements"][0]["type"] = "arrow"
        path = _write_temp(doc)
        result = validate(path)
        assert any("points" in f["issue"] for f in result["findings"])
        Path(path).unlink()

    def test_arrow_insufficient_points(self):
        doc = _valid_doc()
        doc["elements"][0]["type"] = "arrow"
        doc["elements"][0]["points"] = [[0, 0]]
        path = _write_temp(doc)
        result = validate(path)
        assert any("2 points" in f["issue"] for f in result["findings"])
        Path(path).unlink()

    def test_binding_to_nonexistent_element(self):
        doc = _valid_doc()
        doc["elements"][0]["type"] = "arrow"
        doc["elements"][0]["points"] = [[0, 0], [100, 0]]
        doc["elements"][0]["startBinding"] = {
            "elementId": "nonexistent",
            "focus": 0,
            "gap": 1,
        }
        path = _write_temp(doc)
        result = validate(path)
        assert any("non-existent" in f["issue"] for f in result["findings"])
        Path(path).unlink()


class TestStyleValidation:
    def test_invalid_fill_style(self):
        doc = _valid_doc()
        doc["elements"][0]["fillStyle"] = "polka-dots"
        path = _write_temp(doc)
        result = validate(path)
        assert any("fillStyle" in f["issue"] for f in result["findings"])
        Path(path).unlink()

    def test_invalid_stroke_style(self):
        doc = _valid_doc()
        doc["elements"][0]["strokeStyle"] = "wavy"
        path = _write_temp(doc)
        result = validate(path)
        assert any("strokeStyle" in f["issue"] for f in result["findings"])
        Path(path).unlink()


class TestSummary:
    def test_summary_counts(self):
        doc = _valid_doc()
        del doc["elements"][0]["id"]  # critical
        doc["elements"][0]["fillStyle"] = "invalid"  # low
        path = _write_temp(doc)
        result = validate(path)
        assert result["summary"]["total"] >= 2
        assert result["summary"]["critical"] >= 1
        Path(path).unlink()

    def test_warning_status(self):
        doc = _valid_doc()
        # Add arrow with binding to nonexistent element (medium)
        doc["elements"].append({
            "id": "arrow1",
            "type": "arrow",
            "x": 0, "y": 0, "width": 100, "height": 0,
            "points": [[0, 0], [100, 0]],
            "startBinding": {"elementId": "ghost", "focus": 0, "gap": 1},
        })
        path = _write_temp(doc)
        result = validate(path)
        assert result["status"] == "warning"
        Path(path).unlink()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
