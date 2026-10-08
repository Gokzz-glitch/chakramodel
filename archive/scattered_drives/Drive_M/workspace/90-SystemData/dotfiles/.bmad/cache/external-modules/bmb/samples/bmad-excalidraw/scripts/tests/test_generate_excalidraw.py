"""Tests for generate_excalidraw.py"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_excalidraw import (
    generate_excalidraw,
    generate_id,
    layout_grid,
    layout_linear,
    layout_radial,
    make_arrow,
    make_base_element,
    make_frame,
    make_shape,
    make_text,
)


class TestGenerateId:
    def test_length(self):
        assert len(generate_id()) == 8

    def test_uniqueness(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_custom_length(self):
        assert len(generate_id(12)) == 12


class TestMakeBaseElement:
    def test_required_fields(self):
        elem = make_base_element("rectangle", 10, 20, 200, 80)
        assert elem["type"] == "rectangle"
        assert elem["x"] == 10
        assert elem["y"] == 20
        assert elem["width"] == 200
        assert elem["height"] == 80
        assert elem["isDeleted"] is False
        assert isinstance(elem["id"], str)
        assert isinstance(elem["seed"], int)

    def test_overrides(self):
        elem = make_base_element("rectangle", 0, 0, 100, 50, strokeColor="#ff0000")
        assert elem["strokeColor"] == "#ff0000"


class TestMakeShape:
    def test_rectangle_with_text(self):
        shape, text = make_shape("rectangle", 100, 100, "Hello")
        assert shape["type"] == "rectangle"
        assert text["type"] == "text"
        assert text["text"] == "Hello"
        assert text["containerId"] == shape["id"]
        assert any(b["id"] == text["id"] for b in shape["boundElements"])

    def test_diamond(self):
        shape, text = make_shape("diamond", 0, 0, "Decision?")
        assert shape["type"] == "diamond"
        assert shape["width"] == 140 or shape["width"] > 140  # may auto-size

    def test_ellipse(self):
        shape, text = make_shape("ellipse", 0, 0, "Start")
        assert shape["type"] == "ellipse"

    def test_auto_size_long_text(self):
        shape, text = make_shape("rectangle", 0, 0, "This is a very long label text")
        assert shape["width"] >= 200  # should be wider than default

    def test_background_color(self):
        shape, _ = make_shape("rectangle", 0, 0, "Test", bg_color="bg_blue")
        assert shape["backgroundColor"] == "#a5d8ff"


class TestMakeText:
    def test_standalone_text(self):
        text = make_text(50, 50, "Hello World")
        assert text["type"] == "text"
        assert text["text"] == "Hello World"
        assert text["containerId"] is None

    def test_bound_text(self):
        text = make_text(50, 50, "Bound", container_id="shape1")
        assert text["containerId"] == "shape1"

    def test_font_size(self):
        text = make_text(0, 0, "Title", font_size=28)
        assert text["fontSize"] == 28


class TestMakeArrow:
    def test_basic_arrow(self):
        elems = make_arrow(0, 0, 100, 0)
        assert len(elems) >= 1
        arrow = elems[0]
        assert arrow["type"] == "arrow"
        assert arrow["points"] == [[0, 0], [100, 0]]
        assert arrow["endArrowhead"] == "arrow"

    def test_line_style(self):
        elems = make_arrow(0, 0, 100, 0, style="line")
        assert elems[0]["endArrowhead"] is None

    def test_dashed_style(self):
        elems = make_arrow(0, 0, 100, 0, style="dashed")
        assert elems[0]["strokeStyle"] == "dashed"

    def test_with_label(self):
        elems = make_arrow(0, 0, 100, 0, label="yes")
        assert len(elems) == 2  # arrow + label text
        assert elems[1]["type"] == "text"
        assert elems[1]["text"] == "yes"

    def test_with_bindings(self):
        shape1 = make_base_element("rectangle", 0, 0, 200, 80)
        shape1["boundElements"] = []
        shape2 = make_base_element("rectangle", 300, 0, 200, 80)
        shape2["boundElements"] = []

        elems = make_arrow(
            200, 40, 300, 40,
            start_id=shape1["id"], end_id=shape2["id"],
            start_shape=shape1, end_shape=shape2,
        )
        arrow = elems[0]
        assert arrow["startBinding"]["elementId"] == shape1["id"]
        assert arrow["endBinding"]["elementId"] == shape2["id"]
        # Check shapes got updated
        assert any(b["id"] == arrow["id"] for b in shape1["boundElements"])
        assert any(b["id"] == arrow["id"] for b in shape2["boundElements"])


class TestMakeFrame:
    def test_frame(self):
        frame = make_frame(0, 0, 500, 400, "My Frame")
        assert frame["type"] == "frame"
        assert frame["name"] == "My Frame"
        assert frame["width"] == 500


class TestLayoutGrid:
    def test_empty(self):
        assert layout_grid([]) == {}

    def test_single_element(self):
        elems = [{"id": "e1", "type": "rectangle"}]
        pos = layout_grid(elems)
        assert "e1" in pos

    def test_multiple_elements_lr(self):
        elems = [{"id": f"e{i}", "type": "rectangle"} for i in range(4)]
        pos = layout_grid(elems, direction="LR")
        assert len(pos) == 4
        # Elements should have distinct positions
        positions = list(pos.values())
        assert len(set(positions)) == 4

    def test_tb_direction(self):
        elems = [{"id": f"e{i}", "type": "rectangle"} for i in range(4)]
        pos = layout_grid(elems, direction="TB")
        assert len(pos) == 4


class TestLayoutLinear:
    def test_simple_chain(self):
        elems = [
            {"id": "a", "type": "rectangle"},
            {"id": "b", "type": "rectangle"},
            {"id": "c", "type": "rectangle"},
        ]
        conns = [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ]
        pos = layout_linear(elems, conns, direction="LR")
        assert pos["a"][0] < pos["b"][0] < pos["c"][0]  # Left to right

    def test_branching(self):
        elems = [
            {"id": "a", "type": "rectangle"},
            {"id": "b", "type": "rectangle"},
            {"id": "c", "type": "rectangle"},
        ]
        conns = [
            {"from": "a", "to": "b"},
            {"from": "a", "to": "c"},
        ]
        pos = layout_linear(elems, conns, direction="LR")
        # b and c should be at same x level
        assert pos["b"][0] == pos["c"][0]
        # but different y
        assert pos["b"][1] != pos["c"][1]

    def test_tb_direction(self):
        elems = [
            {"id": "a", "type": "rectangle"},
            {"id": "b", "type": "rectangle"},
        ]
        conns = [{"from": "a", "to": "b"}]
        pos = layout_linear(elems, conns, direction="TB")
        assert pos["a"][1] < pos["b"][1]  # Top to bottom

    def test_empty(self):
        assert layout_linear([], []) == {}

    def test_disconnected_elements(self):
        elems = [
            {"id": "a", "type": "rectangle"},
            {"id": "b", "type": "rectangle"},
            {"id": "c", "type": "rectangle"},
        ]
        conns = [{"from": "a", "to": "b"}]
        pos = layout_linear(elems, conns, direction="LR")
        assert len(pos) == 3  # All elements placed including disconnected


class TestLayoutRadial:
    def test_basic(self):
        elems = [
            {"id": "center", "type": "ellipse"},
            {"id": "a", "type": "rectangle"},
            {"id": "b", "type": "rectangle"},
        ]
        conns = [
            {"from": "center", "to": "a"},
            {"from": "center", "to": "b"},
        ]
        pos = layout_radial(elems, conns)
        # Center should be at the center position
        assert pos["center"] == (500, 400)

    def test_empty(self):
        assert layout_radial([], []) == {}


class TestGenerateExcalidraw:
    def test_basic_flowchart(self):
        spec = {
            "title": "Test Flow",
            "type": "flowchart",
            "direction": "LR",
            "elements": [
                {"id": "start", "type": "ellipse", "label": "Start"},
                {"id": "step1", "type": "rectangle", "label": "Step 1"},
                {"id": "end", "type": "ellipse", "label": "End"},
            ],
            "connections": [
                {"from": "start", "to": "step1", "style": "arrow"},
                {"from": "step1", "to": "end", "style": "arrow"},
            ],
        }
        doc = generate_excalidraw(spec)

        assert doc["type"] == "excalidraw"
        assert doc["version"] == 2
        assert isinstance(doc["elements"], list)
        assert len(doc["elements"]) > 0

        # Check element types exist
        types = {e["type"] for e in doc["elements"]}
        assert "ellipse" in types
        assert "rectangle" in types
        assert "arrow" in types
        assert "text" in types

    def test_with_groups(self):
        spec = {
            "type": "architecture",
            "elements": [
                {"id": "svc1", "type": "rectangle", "label": "Service A", "group": "backend"},
                {"id": "svc2", "type": "rectangle", "label": "Service B", "group": "backend"},
            ],
            "connections": [],
            "groups": [
                {"name": "backend", "label": "Backend Services", "type": "frame"},
            ],
        }
        doc = generate_excalidraw(spec)
        types = {e["type"] for e in doc["elements"]}
        assert "frame" in types

    def test_with_decision(self):
        spec = {
            "type": "flowchart",
            "elements": [
                {"id": "start", "type": "rectangle", "label": "Begin"},
                {"id": "decide", "type": "diamond", "label": "OK?"},
                {"id": "yes", "type": "rectangle", "label": "Continue"},
                {"id": "no", "type": "rectangle", "label": "Stop"},
            ],
            "connections": [
                {"from": "start", "to": "decide"},
                {"from": "decide", "to": "yes", "label": "Yes"},
                {"from": "decide", "to": "no", "label": "No"},
            ],
        }
        doc = generate_excalidraw(spec)
        diamonds = [e for e in doc["elements"] if e["type"] == "diamond"]
        assert len(diamonds) == 1

    def test_mindmap(self):
        spec = {
            "type": "mindmap",
            "elements": [
                {"id": "center", "type": "ellipse", "label": "Main Idea"},
                {"id": "b1", "type": "rectangle", "label": "Branch 1"},
                {"id": "b2", "type": "rectangle", "label": "Branch 2"},
            ],
            "connections": [
                {"from": "center", "to": "b1"},
                {"from": "center", "to": "b2"},
            ],
        }
        doc = generate_excalidraw(spec)
        assert doc["type"] == "excalidraw"
        assert len(doc["elements"]) > 0

    def test_output_to_file(self):
        spec = {
            "type": "flowchart",
            "elements": [{"id": "a", "type": "rectangle", "label": "A"}],
            "connections": [],
        }
        doc = generate_excalidraw(spec)

        with tempfile.NamedTemporaryFile(suffix=".excalidraw", delete=False, mode="w") as f:
            json.dump(doc, f)
            tmp_path = f.name

        # Verify it's valid JSON
        loaded = json.loads(Path(tmp_path).read_text())
        assert loaded["type"] == "excalidraw"
        Path(tmp_path).unlink()

    def test_no_title(self):
        spec = {
            "type": "flowchart",
            "elements": [{"id": "a", "type": "rectangle", "label": "A"}],
            "connections": [],
        }
        doc = generate_excalidraw(spec)
        # Should not have a title text element
        texts = [e for e in doc["elements"] if e["type"] == "text" and e.get("containerId") is None]
        assert len(texts) == 0

    def test_empty_spec(self):
        spec = {"type": "flowchart", "elements": [], "connections": []}
        doc = generate_excalidraw(spec)
        assert doc["type"] == "excalidraw"
        assert doc["elements"] == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
