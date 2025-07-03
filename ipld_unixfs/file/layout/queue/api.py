from dataclasses import dataclass
from typing import Mapping, MutableMapping, MutableSequence, Optional, Sequence, Union
from ipld_unixfs.file.layout.api import NodeID
from ipld_unixfs.unixfs import FileLink as FileLink


PropertyKey = Union[str, int]


@dataclass
class LinkedNode:
    id: NodeID
    links: Sequence[FileLink]


@dataclass
class PendingChildren:
    children: Sequence[NodeID]
    count: int


@dataclass
class Queue:
    mutable: bool

    needs: MutableMapping[NodeID, NodeID]
    """Maps link IDs to the node IDs that need them."""

    nodes: MutableMapping[NodeID, PendingChildren]
    """Maps node IDs to the Nodes & a number of links it awaits on."""

    links: MutableMapping[NodeID, FileLink]
    """Available links."""

    linked: Optional[MutableSequence[LinkedNode]] = None
    """List of file nodes that are ready."""


@dataclass
class Delta:
    needs: Optional[Mapping[NodeID, Optional[NodeID]]] = None
    nodes: Optional[Mapping[NodeID, Optional[PendingChildren]]] = None
    links: Optional[Mapping[NodeID, Optional[FileLink]]] = None
    linked: Optional[Sequence[LinkedNode]] = None


@dataclass
class Result(Queue):
    linked: MutableSequence[LinkedNode]
    """List of file nodes that are ready."""
