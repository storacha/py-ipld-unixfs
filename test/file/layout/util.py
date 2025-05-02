import math
from typing import Sequence, TypeVar

from multiformats import CID, multihash
from ipld_unixfs.file.layout.api import NodeID
from ipld_unixfs.file.layout.queue.api import FileLink, LinkedNode


def create_link(name: str, size: int = 120, dag_size: int = -1) -> FileLink:
    if dag_size == -1:
        dag_size = math.floor(size + (size * 15) / 100)
    return FileLink(create_cid(name), dag_size, size)


def create_cid(name: str) -> CID:
    return CID("base32", 1, "raw", multihash.digest(bytes(name, "utf-8"), "sha2-256"))


T = TypeVar("T")


def shuffle(ops: Sequence[T]) -> Sequence[Sequence[T]]:
    """
    Returns given ops in every possible order.
    """
    out: Sequence[Sequence[T]] = []
    for offset in range(len(ops)):
        item = ops[offset]
        rest = list(ops[0:offset])
        rest.extend(ops[offset + 1 :])

        for n in range(len(rest) + 1):
            if n != offset or offset == 0:
                combo = list(rest[0:n])
                combo.append(item)
                combo.extend(rest[n:])
                out.append(combo)
    return out


def create_node(id: NodeID, links: Sequence[FileLink] = []) -> LinkedNode:
    return LinkedNode(id, links)
