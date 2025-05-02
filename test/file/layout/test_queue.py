from typing import Literal, MutableSequence, Sequence, TypedDict, Union
import pytest
from ipld_unixfs.file.layout.api import Branch, Node
import ipld_unixfs.file.layout.queue as Queue
from ipld_unixfs.file.layout.queue.api import PendingChildren, Result, FileLink
from test.file.layout.util import create_link, create_node, shuffle


def test_empty_is_linked_right_away() -> None:
    v0 = Queue.empty()
    v1 = Queue.add_node(Branch(0, []), v0)

    assert v1 == Result(
        mutable=False,
        needs={},
        links={},
        nodes={},
        linked=[create_node(0, [])],
    )


def test_has_only_one_link() -> None:
    v0 = Queue.empty()
    v1 = Queue.add_link(1, create_link("a"), v0)
    v2 = Queue.add_node(Branch(0, [1]), v1)

    assert v2 == Result(
        mutable=False,
        needs={},
        links={},
        nodes={},
        linked=[create_node(0, [create_link("a")])],
    )


def test_has_several_links() -> None:
    v0 = Queue.add_links(
        [
            (1, create_link("a")),
            (2, create_link("b")),
            (3, create_link("c")),
        ],
        Queue.empty(),
    )

    v1 = Queue.add_node(Branch(0, [1, 2, 3]), v0)

    assert v1 == Result(
        mutable=False,
        needs={},
        links={},
        nodes={},
        linked=[create_node(0, [create_link("a"), create_link("b"), create_link("c")])],
    )


def test_needs_first_child() -> None:
    v0 = Queue.empty()
    assert Queue.is_empty(v0) is True

    v1 = Queue.add_node(Branch(0, [1]), v0)

    assert Queue.is_empty(v1) is False
    assert Queue.is_empty(v0) is True

    assert v1 == Result(
        mutable=False,
        needs={1: 0},
        links={},
        nodes={0: PendingChildren([1], 1)},
        linked=[],
    ), "adds node to the queue"

    v2 = Queue.add_link(1, create_link("foo"), v1)

    assert v2 == Result(
        mutable=False,
        needs={},
        links={},
        nodes={},
        linked=[create_node(0, [create_link("foo")])],
    ), "moves node to the ready list"


def test_queue_then_link() -> None:
    v0 = Queue.add_links(
        [
            (2, create_link("b")),
            (4, create_link("d")),
        ],
        Queue.empty(),
    )

    v1 = Queue.add_node(Branch(9, [1, 2, 3, 4, 5]), v0)

    assert v1 == Result(
        mutable=False,
        needs={1: 9, 3: 9, 5: 9},
        links={2: create_link("b"), 4: create_link("d")},
        nodes={9: PendingChildren([1, 2, 3, 4, 5], 3)},
        linked=[],
    ), "adds node to the queue"

    v2 = Queue.add_link(1, create_link("a"), v1)

    assert v2 == Result(
        mutable=False,
        needs={3: 9, 5: 9},
        links={1: create_link("a"), 2: create_link("b"), 4: create_link("d")},
        nodes={9: PendingChildren([1, 2, 3, 4, 5], 2)},
        linked=[],
    ), "removes first depedency"

    v3 = Queue.add_link(5, create_link("e"), v2)

    assert v3 == Result(
        mutable=False,
        needs={3: 9},
        links={
            1: create_link("a"),
            2: create_link("b"),
            4: create_link("d"),
            5: create_link("e"),
        },
        nodes={9: PendingChildren([1, 2, 3, 4, 5], 1)},
        linked=[],
    ), "removes last depedency"

    v4 = Queue.add_link(3, create_link("c"), v3)

    assert v4 == Result(
        mutable=False,
        needs={},
        links={},
        nodes={},
        linked=[
            create_node(
                9,
                [
                    create_link("a"),
                    create_link("b"),
                    create_link("c"),
                    create_link("d"),
                    create_link("e"),
                ],
            )
        ],
    ), "moves to linked"


def test_links_ahead() -> None:
    v0 = Queue.add_links(
        [
            (2, create_link("b")),
            (5, create_link("d")),
        ],
        Queue.empty(),
    )

    v1 = Queue.add_node(Branch(9, [1, 2, 3, 5, 4]), v0)

    assert v1 == Result(
        mutable=False,
        needs={1: 9, 3: 9, 4: 9},
        links={2: create_link("b"), 5: create_link("d")},
        nodes={9: PendingChildren([1, 2, 3, 5, 4], 3)},
        linked=[],
    ), "adds node to the queue"

    v2 = Queue.add_link(1, create_link("a"), v1)

    assert v2 == Result(
        mutable=False,
        needs={3: 9, 4: 9},
        links={1: create_link("a"), 2: create_link("b"), 5: create_link("d")},
        nodes={9: PendingChildren([1, 2, 3, 5, 4], 2)},
        linked=[],
    ), "removes first depedency"

    v3 = Queue.add_link(4, create_link("e"), v2)

    assert v3 == Result(
        mutable=False,
        needs={3: 9},
        links={
            1: create_link("a"),
            2: create_link("b"),
            4: create_link("e"),
            5: create_link("d"),
        },
        nodes={9: PendingChildren([1, 2, 3, 5, 4], 1)},
        linked=[],
    ), "removes last depedency"

    v4 = Queue.add_link(3, create_link("c"), v3)

    assert v4 == Result(
        mutable=False,
        needs={},
        links={},
        nodes={},
        linked=[
            create_node(
                9,
                [
                    create_link("a"),
                    create_link("b"),
                    create_link("c"),
                    create_link("d"),
                    create_link("e"),
                ],
            )
        ],
    ), "moves to linked"


Op = Union[
    TypedDict("AddNodeOp", {"type": Literal["addNode"], "node": Node}),
    TypedDict("AddLinkOp", {"type": Literal["addLink"], "id": int, "link": FileLink}),
]

ops: Sequence[Op] = [
    {"type": "addNode", "node": Branch(9, [1, 2, 3, 4, 5])},
    {"type": "addLink", "id": 1, "link": create_link("a")},
    {"type": "addLink", "id": 2, "link": create_link("b")},
    {"type": "addLink", "id": 3, "link": create_link("c")},
    {"type": "addLink", "id": 4, "link": create_link("d")},
    {"type": "addLink", "id": 5, "link": create_link("e")},
    {"type": "addNode", "node": Branch(7, [6])},
    {"type": "addLink", "id": 6, "link": create_link("f")},
    {"type": "addNode", "node": Branch(0, [8, 9, 10, 11])},
    {"type": "addLink", "id": 8, "link": create_link("g")},
    {"type": "addLink", "id": 9, "link": create_link("h")},
    {"type": "addLink", "id": 10, "link": create_link("M")},
    {"type": "addLink", "id": 11, "link": create_link("n")},
]

orders: Sequence[Sequence[Op]] = shuffle(ops)
titles: Sequence[str] = []

for order in orders:
    title: MutableSequence[str] = []
    for op in order:
        if op.get("type") == "addLink":
            title.append("addLink(" + str(op.get("id")) + ")")
        else:
            title.append("addNode(" + str(op.get("node").id) + ")")
    titles.append(".".join(title))


@pytest.mark.parametrize("order", orders, ids=titles)
def test_random_operation_order(order: Sequence[Op]) -> None:
    queue = Queue.empty()
    for op in order:
        if op.get("type") == "addLink":
            queue = Queue.add_link(op.get("id"), op.get("link"), queue)
        else:
            queue = Queue.add_node(op.get("node"), queue)

    assert Result(
        mutable=queue.mutable,
        needs=queue.needs,
        links=queue.links,
        nodes=queue.nodes,
        linked=[],
    ) == Result(mutable=False, needs={}, links={}, nodes={}, linked=[])

    expectedLinks = [
        create_node(
            9,
            [
                create_link("a"),
                create_link("b"),
                create_link("c"),
                create_link("d"),
                create_link("e"),
            ],
        ),
        create_node(7, [create_link("f")]),
        create_node(
            0,
            [
                create_link("g"),
                create_link("h"),
                create_link("M"),
                create_link("n"),
            ],
        ),
    ].sort(key=lambda l: len(l.links))

    assert list(queue.linked).sort(key=lambda l: len(l.links)) == expectedLinks
