"""
Round 34 Target 4: the penta-desk canvas.

A JSON Canvas with the tax reserve at the centre and the five desks around it,
gated one way and flowing back the other. The tests pin that it is valid JSON
Canvas (every edge references a node), that file nodes only ever point at notes
that exist, that the centre is the NEWEST tax note, that it is stable across
re-runs, and that the hub links to it with a link that resolves.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics import obsidian_links as links

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
DESKS = ("hl", "pm", "ql", "sports", "xarb")


def _canvas(vault):
    path, written = links.write_penta_canvas(vault)
    return path, written, json.loads(path.read_text(encoding="utf-8"))


def test_the_canvas_is_written_into_an_empty_vault_and_is_stable(tmp_path):
    path, written, data = _canvas(tmp_path)
    assert written
    assert path == tmp_path / "Canvases" / "Sovereign_Penta_Cockpit.canvas"
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"hub", "tax", *DESKS}
    assert all(n["type"] == "text" for n in data["nodes"])          # nothing exported yet
    for edge in data["edges"]:
        assert edge["fromNode"] in ids and edge["toNode"] in ids
    assert len({e["id"] for e in data["edges"]}) == len(data["edges"])
    # Nothing volatile in the content, so the second write is a no-op.
    assert links.write_penta_canvas(tmp_path) == (path, False)


def test_file_nodes_point_at_notes_that_exist_and_the_centre_is_the_newest_tax_note(tmp_path):
    (tmp_path / "Sports_Desk.md").write_text("# sports", encoding="utf-8")
    (tmp_path / "HyperLiquid_Monarch.md").write_text("# hl", encoding="utf-8")
    taxes = tmp_path / "Trading_Taxes"
    taxes.mkdir()
    (taxes / "Tax_Reserve_2026-09-02.md").write_text("old", encoding="utf-8")
    (taxes / "Tax_Reserve_2026-09-03.md").write_text("new", encoding="utf-8")

    _, _, data = _canvas(tmp_path)
    nodes = {n["id"]: n for n in data["nodes"]}
    assert nodes["sports"]["type"] == "file" and nodes["sports"]["file"] == "Sports_Desk.md"
    assert nodes["hl"]["file"] == "HyperLiquid_Monarch.md"
    assert nodes["tax"]["file"] == "Trading_Taxes/Tax_Reserve_2026-09-03.md"
    assert nodes["pm"]["type"] == "text" and "not exported" in nodes["pm"]["text"]
    for node in nodes.values():
        if node["type"] == "file":
            assert (tmp_path / node["file"]).exists(), node["file"]

    # A new day's tax note moves the centre, and that is a real change.
    (taxes / "Tax_Reserve_2026-09-04.md").write_text("newer", encoding="utf-8")
    _, written, data = _canvas(tmp_path)
    assert written
    assert {n["id"]: n for n in data["nodes"]}["tax"]["file"].endswith("2026-09-04.md")


def test_every_desk_is_gated_by_the_reserve_and_flows_back_to_it(tmp_path):
    _, _, data = _canvas(tmp_path)
    edges = data["edges"]
    for desk in DESKS:
        gate = [e for e in edges if e["fromNode"] == "tax" and e["toNode"] == desk]
        flow = [e for e in edges if e["fromNode"] == desk and e["toNode"] == "tax"]
        assert len(gate) == 1 and "capital gate" in gate[0]["label"], desk
        assert len(flow) == 1 and "reserve" in flow[0]["label"], desk
    assert any(e["fromNode"] == "sports" and e["toNode"] == "xarb" for e in edges)
    assert any(e["fromNode"] == "pm" and e["toNode"] == "xarb" for e in edges)
    assert any(e["fromNode"] == "hub" and e["toNode"] == "tax" for e in edges)


def test_the_hub_links_to_the_canvas_and_the_link_resolves(tmp_path):
    hub = links.write_hub_note(tmp_path, "2026-09-04 00:00:00 UTC")
    canvas = tmp_path / "Canvases" / "Sovereign_Penta_Cockpit.canvas"
    assert canvas.exists()
    text = hub.read_text(encoding="utf-8")
    assert "[[Canvases/Sovereign_Penta_Cockpit.canvas|" in text
    for target in WIKILINK.findall(text):
        t = target.strip()
        assert ((tmp_path / t).exists() or (tmp_path / (t + ".md")).exists()
                or any(p.stem == t for p in tmp_path.rglob("*.md"))), t
