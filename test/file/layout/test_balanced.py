from ipld_unixfs.file.layout.api import Branch, Leaf
import ipld_unixfs.file.layout.balanced as Balanced
from ipld_unixfs.file.chunker.buffer import BufferView


def test_empty_produces_empty_leaf_node() -> None:
    layout = Balanced.open()
    result = Balanced.close(layout)
    assert result.root.id == 1
    assert result.root.metadata is None
    assert list(result.nodes) == []
    assert list(result.leaves) == []


def test_single_leaf_does_not_produce_root() -> None:
    layout = Balanced.open()
    result = Balanced.write(layout, [BufferView.create([[0, 1, 2, 3]])])
    assert list(result.nodes) == []
    assert list(result.leaves) == []

    result = Balanced.close(result.layout)
    assert result.root.id == 1
    assert result.root.content == BufferView.create([[0, 1, 2, 3]])
    assert result.root.metadata is None


def test_two_leaves_produce_a_root() -> None:
    file = [0, 1, 2, 3, 4, 5, 6, 7]
    layout = Balanced.open()
    result = Balanced.write(
        layout,
        [
            BufferView.create([file[0:4]]),
            BufferView.create([file[4:8]]),
        ],
    )
    assert list(result.nodes) == []
    assert result.leaves == [
        Leaf(1, BufferView.create([file[0:4]]), None),
        Leaf(2, BufferView.create([file[4:8]]), None),
    ]

    result = Balanced.close(result.layout)
    assert result.root == Branch(3, [1, 2], None)
    assert list(result.nodes) == []
    assert list(result.leaves) == []
