import pytest
from ipld_unixfs.file.layout.api import Branch
import ipld_unixfs.file.layout.queue as Queue
from ipld_unixfs.file.layout.queue.api import PendingChildren, Result
from test.file.layout.util import create_link, create_node


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


# describe("layout queue", () => {
#   it("queu then link", () => {
#     const v0 = Queue.addLinks(
#       [
#         [2, createLink("b")],
#         [4, createLink("d")],
#       ],
#       Queue.empty()
#     )

#     const v1 = Queue.addNode(
#       {
#         id: 9,
#         children: [1, 2, 3, 4, 5],
#       },
#       v0
#     )

#     assert.deepEqual(
#       v1,
#       {
#         mutable: false,
#         needs: { [1]: 9, [3]: 9, [5]: 9 },
#         links: {
#           [2]: createLink("b"),
#           [4]: createLink("d"),
#         },
#         nodes: {
#           [9]: {
#             count: 3,
#             children: [1, 2, 3, 4, 5],
#           },
#         },
#         linked: [],
#       },
#       "adds node to the queue"
#     )

#     const v2 = Queue.addLink(1, createLink("a"), v1)

#     assert.deepEqual(
#       v2,
#       {
#         mutable: false,
#         needs: { [3]: 9, [5]: 9 },
#         links: {
#           [1]: createLink("a"),
#           [2]: createLink("b"),
#           [4]: createLink("d"),
#         },
#         nodes: {
#           [9]: {
#             count: 2,
#             children: [1, 2, 3, 4, 5],
#           },
#         },
#         linked: [],
#       },
#       "removes first depedency"
#     )

#     const v3 = Queue.addLink(5, createLink("e"), v2)

#     assert.deepEqual(
#       v3,
#       {
#         mutable: false,
#         needs: { [3]: 9 },
#         links: {
#           [1]: createLink("a"),
#           [2]: createLink("b"),
#           [4]: createLink("d"),
#           [5]: createLink("e"),
#         },
#         nodes: {
#           [9]: {
#             count: 1,
#             children: [1, 2, 3, 4, 5],
#           },
#         },
#         linked: [],
#       },
#       "removes last depedency"
#     )

#     const v4 = Queue.addLink(3, createLink("c"), v3)

#     assert.deepEqual(
#       v4,
#       {
#         mutable: false,
#         needs: {},
#         links: {},
#         nodes: {},
#         linked: [
#           createNode(9, [
#             createLink("a"),
#             createLink("b"),
#             createLink("c"),
#             createLink("d"),
#             createLink("e"),
#           ]),
#         ],
#       },
#       "moves to linked"
#     )
#   })

#   it("links ahead", () => {
#     const v0 = Queue.addLinks(
#       [
#         [2, createLink("b")],
#         [5, createLink("d")],
#       ],
#       Queue.empty()
#     )

#     const v1 = Queue.addNode(
#       {
#         id: 9,
#         children: [1, 2, 3, 5, 4],
#       },
#       v0
#     )

#     assert.deepEqual(
#       v1,
#       {
#         mutable: false,
#         needs: { [1]: 9, [3]: 9, [4]: 9 },
#         links: {
#           [2]: createLink("b"),
#           [5]: createLink("d"),
#         },
#         nodes: {
#           [9]: {
#             count: 3,
#             children: [1, 2, 3, 5, 4],
#           },
#         },
#         linked: [],
#       },
#       "adds node to the queue"
#     )

#     const v2 = Queue.addLink(1, createLink("a"), v1)

#     assert.deepEqual(
#       v2,
#       {
#         mutable: false,
#         needs: { [3]: 9, [4]: 9 },
#         links: {
#           [1]: createLink("a"),
#           [2]: createLink("b"),
#           [5]: createLink("d"),
#         },
#         nodes: {
#           [9]: {
#             count: 2,
#             children: [1, 2, 3, 5, 4],
#           },
#         },
#         linked: [],
#       },
#       "removes first depedency"
#     )

#     const v3 = Queue.addLink(4, createLink("e"), v2)

#     assert.deepEqual(
#       v3,
#       {
#         mutable: false,
#         needs: { [3]: 9 },
#         links: {
#           [1]: createLink("a"),
#           [2]: createLink("b"),
#           [4]: createLink("e"),
#           [5]: createLink("d"),
#         },
#         nodes: {
#           [9]: {
#             count: 1,
#             children: [1, 2, 3, 5, 4],
#           },
#         },
#         linked: [],
#       },
#       "removes last depedency"
#     )

#     const v4 = Queue.addLink(3, createLink("c"), v3)

#     assert.deepEqual(
#       v4,
#       {
#         mutable: false,
#         needs: {},
#         links: {},
#         nodes: {},
#         linked: [
#           createNode(9, [
#             createLink("a"),
#             createLink("b"),
#             createLink("c"),
#             createLink("d"),
#             createLink("e"),
#           ]),
#         ],
#       },
#       "moves to linked"
#     )
#   })
# })

# describe("random operation order", () => {
#   /** @type {Array<{type:"addNode", node: Queue.Node}|{type:"addLink", id:number, link:Queue.Link}>} */
#   const ops = [
#     {
#       type: "addNode",
#       node: {
#         id: 9,
#         children: [1, 2, 3, 4, 5],
#       },
#     },
#     {
#       type: "addLink",
#       id: 1,
#       link: createLink("a"),
#     },
#     {
#       type: "addLink",
#       id: 2,
#       link: createLink("b"),
#     },
#     {
#       type: "addLink",
#       id: 3,
#       link: createLink("c"),
#     },
#     {
#       type: "addLink",
#       id: 4,
#       link: createLink("d"),
#     },
#     {
#       type: "addLink",
#       id: 5,
#       link: createLink("e"),
#     },
#     {
#       type: "addNode",
#       node: {
#         id: 7,
#         children: [6],
#       },
#     },
#     {
#       type: "addLink",
#       id: 6,
#       link: createLink("f"),
#     },
#     {
#       type: "addNode",
#       node: {
#         id: 0,
#         children: [8, 9, 10, 11],
#       },
#     },
#     {
#       type: "addLink",
#       id: 8,
#       link: createLink("g"),
#     },
#     {
#       type: "addLink",
#       id: 9,
#       link: createLink("h"),
#     },
#     {
#       type: "addLink",
#       id: 10,
#       link: createLink("M"),
#     },
#     {
#       type: "addLink",
#       id: 11,
#       link: createLink("n"),
#     },
#   ]

#   for (const order of shuffle(ops)) {
#     const title = `${order
#       .map(op =>
#         op.type === "addLink"
#           ? `addLink(${op.id})`
#           : `addNode(${String(op.node.id)})`
#       )
#       .join(".")}`

#     it(title, () => {
#       let queue = Queue.empty()
#       for (const op of order) {
#         queue =
#           op.type === "addLink"
#             ? Queue.addLink(op.id, op.link, queue)
#             : Queue.addNode(op.node, queue)
#       }

#       assert.deepEqual(
#         { ...queue, linked: [] },
#         {
#           mutable: false,
#           needs: {},
#           links: {},
#           nodes: {},
#           linked: [],
#         }
#       )

#       const expectedLinks = [
#         createNode(9, [
#           createLink("a"),
#           createLink("b"),
#           createLink("c"),
#           createLink("d"),
#           createLink("e"),
#         ]),
#         createNode(7, [createLink("f")]),
#         createNode(0, [
#           createLink("g"),
#           createLink("h"),
#           createLink("M"),
#           createLink("n"),
#         ]),
#       ]

#       assert.deepEqual(
#         [...queue.linked].sort((a, b) => a.links.length - b.links.length),
#         expectedLinks.sort((a, b) => a.links.length - b.links.length)
#       )
#     })
#   }
# })
