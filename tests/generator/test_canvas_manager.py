import json

from src.generator.canvas_manager import CanvasManager


class TestCanvasManager:
    def test_add_node(self):
        manager = CanvasManager()
        node_id = manager.add_node(node_type="text", x=100, y=200, width=300, height=400, text="Hello World", color="1")

        assert len(manager.nodes) == 1
        node = manager.nodes[0]
        assert node["id"] == node_id
        assert node["x"] == 100
        assert node["y"] == 200
        assert node["width"] == 300
        assert node["height"] == 400
        assert node["type"] == "text"
        assert node["text"] == "Hello World"
        assert node["color"] == "1"

    def test_add_group_node(self):
        manager = CanvasManager()
        manager.add_node(node_type="group", x=0, y=0, width=500, height=500, label="My Group")

        assert len(manager.nodes) == 1
        assert manager.nodes[0]["label"] == "My Group"

    def test_add_edge(self):
        manager = CanvasManager()
        node1 = manager.add_node("text", 0, 0, 100, 100, text="Node 1")
        node2 = manager.add_node("text", 200, 0, 100, 100, text="Node 2")

        edge_id = manager.add_edge(from_node=node1, from_side="right", to_node=node2, to_side="left", label="Connects")

        assert len(manager.edges) == 1
        edge = manager.edges[0]
        assert edge["id"] == edge_id
        assert edge["fromNode"] == node1
        assert edge["toNode"] == node2
        assert edge["label"] == "Connects"

    def test_generate_json(self):
        manager = CanvasManager()
        manager.add_node("text", 0, 0, 100, 100, text="test")
        json_output = manager.generate_json()

        data = json.loads(json_output)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
