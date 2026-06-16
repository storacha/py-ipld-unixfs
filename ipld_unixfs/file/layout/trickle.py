from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Sequence
from ipld_unixfs.file.chunker.interfaces import Chunk
from ipld_unixfs.file.layout.interfaces import (
    Branch,
    CloseResult,
    LayoutEngine,
    Leaf,
    NodeID,
    WriteResult
)
from ipld_unixfs.unixfs import Metadata

EMPTY = ()

@dataclass(frozen=True, slots=True)
class Options:
    max_sibling_subgroups: int = 4
    max_direct_leaves: int = 174
    unixfs_nul_leaf_compat: bool = True

defaults = Options()

class TrickleNode:
    depth: int
    direct_leaves: List[NodeID]
    parent: TrickleNode

    def __init__(self, depth: int, direct_leaves: List[NodeID], parent: Optional[TrickleNode] = None):
        self.depth = depth
        self.direct_leaves = direct_leaves
        self.parent = parent if parent is not None else self

    def append(self, leaf: NodeID) -> TrickleNode:
        return TrickleNode(
            depth=self.depth,
            direct_leaves=self.direct_leaves + [leaf],
            parent=self.parent
        )

@dataclass
class Trickle:
    options: Options
    leaf_count: int
    level_cutoffs: List[int]
    tail: TrickleNode
    last_id: int

class TrickleLayout(LayoutEngine[Trickle]):
    def __init__(self, options: Options = defaults):
        self.options = options

    def open(self) -> Trickle:
        return open_layout(self.options)

    def write(self, layout: Trickle, chunks: Sequence[Chunk]) -> WriteResult[Trickle]:
        return write(layout, chunks)

    def close(self, layout: Trickle, metadata: Optional[Metadata] = None) -> CloseResult:
        return close(layout, metadata)

def ronfigure(
    max_sibling_subgroups: int = 4,
    max_direct_leaves: int = 174,
    unixfs_nul_leaf_compat: bool = False,
) -> LayoutEngine[Trickle]:
    return TrickleLayout(Options(
        max_sibling_subgroups=max_sibling_subgroups,
        max_direct_leaves=max_direct_leaves,
        unixfs_nul_leaf_compat=unixfs_nul_leaf_compat
    ))

def open_layout(options: Options = defaults) -> Trickle:
    parent = TrickleNode(depth=-1, direct_leaves=[])
    tail = TrickleNode(depth=0, direct_leaves=[], parent=parent)
    return Trickle(
        options=options,
        leaf_count=0,
        level_cutoffs=[options.max_direct_leaves],
        tail=tail,
        last_id=0
    )

def write(layout: Trickle, chunks: Sequence[Chunk]) -> WriteResult[Trickle]:
    current_layout = layout
    nodes: List[Branch] = []
    leaves: List[Leaf] = []
    
    for chunk in chunks:
        if len(chunk) > 0:
            current_layout.last_id += 1
            leaf = Leaf(current_layout.last_id, chunk, None)
            leaves.append(leaf)
            
            result = _add_leaf(current_layout, nodes, leaves, leaf.id)
            current_layout = result.layout
            nodes = list(result.nodes)
            leaves = list(result.leaves)
            
    return WriteResult(current_layout, nodes, leaves)

def _add_leaf(layout: Trickle, nodes: List[Branch], leaves: List[Leaf], leaf_id: NodeID) -> WriteResult[Trickle]:
    if layout.leaf_count == 0 or layout.leaf_count % layout.options.max_direct_leaves != 0:
        return WriteResult(_push_leaf(layout, leaf_id), nodes, leaves)
    else:
        depth, level_cutoffs = _find_next_leaf_target(layout)
        
        current_layout = layout
        current_nodes = nodes
        current_leaves = leaves
        
        if layout.tail.depth >= depth:
            seal_result = _seal_to_level(layout, current_nodes, current_leaves, depth)
            current_layout = seal_result.layout
            current_nodes = list(seal_result.nodes)
            current_leaves = list(seal_result.leaves)
        
        current_layout.level_cutoffs = level_cutoffs
        current_layout.tail = TrickleNode(
            depth=depth,
            direct_leaves=[leaf_id],
            parent=current_layout.tail
        )
        current_layout.leaf_count += 1
        
        return WriteResult(current_layout, current_nodes, current_leaves)

def _find_next_leaf_target(layout: Trickle) -> tuple[int, List[int]]:
    leaf_count = layout.leaf_count
    level_cutoffs = list(layout.level_cutoffs)
    options = layout.options
    
    if leaf_count == level_cutoffs[-1]:
        cutoff = options.max_direct_leaves * (
            (options.max_sibling_subgroups + 1) ** len(level_cutoffs)
        )
        level_cutoffs.append(cutoff)
        return 1, level_cutoffs
    else:
        depth = 0
        remaining_leaves = leaf_count
        level = len(level_cutoffs) - 1
        while level >= 0:
            if remaining_leaves >= level_cutoffs[level]:
                depth += 1
            remaining_leaves %= level_cutoffs[level]
            level -= 1
        return depth, level_cutoffs

def _push_leaf(layout: Trickle, leaf_id: NodeID) -> Trickle:
    layout.tail = layout.tail.append(leaf_id)
    layout.leaf_count += 1
    return layout

def _seal_to_level(layout: Trickle, nodes: List[Branch], leaves: List[Leaf], depth: int) -> WriteResult[Trickle]:
    depth = max(0, depth)
    current_nodes = list(nodes)
    tail = layout.tail
    last_id = layout.last_id
    
    while tail.depth >= depth:
        parent = tail.parent
        last_id += 1
        node = Branch(last_id, tail.direct_leaves, None)
        current_nodes.append(node)
        
        tail = TrickleNode(
            depth=parent.depth,
            direct_leaves=parent.direct_leaves + [node.id],
            parent=parent.parent
        )
        
        if tail.depth == -1:
            break

    layout.last_id = last_id
    layout.tail = tail
    return WriteResult(layout, current_nodes, leaves)

def close(layout: Trickle, metadata: Optional[Metadata] = None) -> CloseResult:
    if layout.options.unixfs_nul_leaf_compat and layout.leaf_count == 0:
        root = Leaf(layout.last_id + 1, None, metadata, None)
        return CloseResult(root, EMPTY, EMPTY)
    else:
        seal_result = _seal_to_level(layout, [], [], 0)
        nodes = list(seal_result.nodes)
        root_branch = nodes.pop()
        
        return CloseResult(
            root=Branch(root_branch.id, root_branch.children, metadata),
            nodes=nodes,
            leaves=EMPTY
        )
