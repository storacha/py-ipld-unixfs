from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Union
from ipld_unixfs.file.layout.api import NodeID
from ipld_unixfs.unixfs import FileLink

PropertyKey = Union[str, int]


@dataclass
class LinkedNode:
    id: NodeID
    links: Sequence[FileLink]


@dataclass
class PendingChildren:
    children: Sequence[NodeID]
    count: int


class Queue:
    mutable: bool

    needs: dict[NodeID, NodeID]
    """Maps link IDs to the node IDs that need them."""

    nodes: dict[NodeID, PendingChildren]
    """Maps node IDs to the Nodes & a number of links it awaits on."""

    links: dict[NodeID, FileLink]
    """Available links."""

    linked: Optional[list[LinkedNode]]
    """List of file nodes that are ready."""

    def __init__(
        self,
        mutable: bool,
        needs: dict[NodeID, NodeID],
        nodes: dict[NodeID, PendingChildren],
        links: dict[NodeID, FileLink],
        linked: Optional[list[LinkedNode]] = None,
    ):
        self.mutable = mutable
        self.needs = needs
        self.nodes = nodes
        self.links = links
        self.linked = linked


class Delta:
    needs: Optional[dict[NodeID, Optional[NodeID]]]
    nodes: Optional[dict[NodeID, Optional[PendingChildren]]]
    links: Optional[dict[NodeID, Optional[FileLink]]]
    linked: Optional[list[LinkedNode]]


class Result(Queue):
    linked: Sequence[LinkedNode]
    """List of file nodes that are ready."""

    def __init__(
        self,
        mutable: bool,
        needs: dict[NodeID, NodeID],
        nodes: dict[NodeID, PendingChildren],
        links: dict[NodeID, FileLink],
        linked: list[LinkedNode],
    ):
        super().__init__(mutable, needs, nodes, links, linked)
