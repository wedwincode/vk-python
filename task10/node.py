from __future__ import annotations

import gc


class GraphNode:
    def __init__(
        self,
        id: int,
        neighbors: list | None = None,
        meta: dict | None = None,
    ) -> None:
        self.id = id
        self.neighbors = neighbors if neighbors is not None else []
        self.meta = meta if meta is not None else {}


def control_gc_cycles() -> tuple[bool, int, bool]:
    gc.disable()

    node1 = GraphNode(1)
    node2 = GraphNode(2)

    node1.neighbors.append(node2)
    node2.neighbors.append(node1)

    node1.meta["self"] = node1
    node2.meta["self"] = node2

    node1_id = id(node1)
    node2_id = id(node2)

    exists_before_collect = any(
        id(obj) in {node1_id, node2_id}
        for obj in gc.get_objects()
    )

    del node1
    del node2

    collected_count = gc.collect()

    gc.enable()

    exists_after_collect = any(
        id(obj) in {node1_id, node2_id}
        for obj in gc.get_objects()
    )

    return exists_before_collect, collected_count, exists_after_collect


def apply_gc_policy() -> tuple[int, int, int]:
    gc.set_threshold(300, 8, 4)
    return gc.get_threshold()
