from ipld_unixfs import codec, unixfs
MURMUR = 0x22

class TestUnixfsFormat:
    def test_encodes_simple_file(self):
        block = codec.encode(
            unixfs.SimpleFile(
                content="batata".encode(),
                type=unixfs.NodeType.File,
                layout="simple"
            )
        )

        node = codec.decode(block)
        assert node == unixfs.SimpleFile(
            type=unixfs.NodeType.File,
            layout="simple",
            metadata=unixfs.Metadata(),
            content="batata".encode(),
        )

    def test_raw(self):
        block = codec.encode(
            node=unixfs.Raw(type=unixfs.NodeType.Raw, content="bananas".encode())
        )
        node = codec.decode(block)

        assert node.type is unixfs.NodeType.Raw, "expected raw"
        assert node.content == "bananas".encode()
        assert codec.file_size(node) == 7

    def test_directory(self):
        block = codec.encode(
            unixfs.FlatDirectory(
                type=unixfs.NodeType.Directory,
                entries=[],
                metadata=unixfs.Metadata(),
            )
        )
        node = codec.decode(block)
        assert node.type is unixfs.NodeType.Directory, "expected dir"
        assert node.entries == ()
        assert codec.file_size(node) == 0

    def test_hamt_sharded_directory(self):
        block = codec.encode(
            unixfs.DirectoryShard(
                bitfield=bytes(),
                type=unixfs.NodeType.HAMTShard,
                fanout=8,
                hash_type=MURMUR,
                entries=[]
            )
        )
        node = codec.decode(block)
        assert node.type == unixfs.NodeType.HAMTShard, "expected HAMT"
        assert node.fanout == 8
        assert node.hash_type == MURMUR
        assert node.entries == ()
        assert node.bitfield == bytes()
        assert codec.file_size(node) == 0

    def test_mode(self):
        mode = 0o755
        block = codec.encode(
            unixfs.SimpleFile(
                type=unixfs.NodeType.File,
                layout="simple",
                metadata=unixfs.Metadata(mode),
                content="mode".encode()
            )
        )

        node = codec.decode(block)
        assert node == unixfs.SimpleFile(
            type=unixfs.NodeType.File,
            layout="simple",
            metadata=unixfs.Metadata(mode),
            content="mode".encode()
        )

    def test_omit_default_file_mode(self):
        block = codec.encode(
            unixfs.SimpleFile(
                type=unixfs.NodeType.File,
                layout="simple",
                metadata=unixfs.Metadata(mode=0o644),
                content="0644".encode()
            )
        )

        assert codec.decode(block) == unixfs.SimpleFile(
            type=unixfs.NodeType.File,
            layout="simple",
            metadata=unixfs.Metadata(),
            content="0644".encode()
        )

    def test_dir_mode(self):
        block = codec.encode(
            unixfs.FlatDirectory(
                entries=[],
                type=unixfs.NodeType.Directory,
                metadata=unixfs.Metadata(mode=0o775)
            )
        )

        assert codec.decode(block) == unixfs.FlatDirectory(
            type=unixfs.NodeType.Directory,
            metadata=unixfs.Metadata(mode=0o775),
            entries=(),
        )

    def test_omits_default_dir_mode(self):
        block = codec.encode(
            unixfs.FlatDirectory(
                type=unixfs.NodeType.Directory,
                metadata=unixfs.Metadata(mode=0o755),
                entries=[]
            )
        )
        assert codec.decode(block) == unixfs.FlatDirectory(
            type=unixfs.NodeType.Directory,
            metadata=unixfs.Metadata(),
            entries=()
        )

    def test_hamt_mode(self):
        block = codec.encode(
            unixfs.ShardedDirectory(
                bitfield=bytes(),
                fanout=16,
                hash_type=MURMUR,
                entries=[],
                type=unixfs.NodeType.HAMTShard,
                metadata=unixfs.Metadata(mode=0o775)
            )
        )

        assert codec.decode(block) == unixfs.ShardedDirectory(
            type=unixfs.NodeType.HAMTShard,
            metadata=unixfs.Metadata(0o775),
            bitfield=bytes(),
            fanout=16,
            hash_type=MURMUR,
            entries=(),
        )

    def test_omits_default_hamt_mode(self):
        block = codec.encode(
            unixfs.ShardedDirectory(
                type=unixfs.NodeType.HAMTShard,
                metadata=unixfs.Metadata(0o755),
                bitfield=bytes(),
                fanout=128,
                hash_type=MURMUR,
                entries=[]
            )
        )

        assert codec.decode(block) == unixfs.ShardedDirectory(
            type=unixfs.NodeType.HAMTShard,
            bitfield=bytes(),
            fanout=128,
            hash_type=MURMUR,
            entries=(),
            metadata=unixfs.Metadata()
        )

    def test_mtime(self):
        mtime = unixfs.MTime(secs=5, nsecs=0)
        block = codec.encode(
            unixfs.SimpleFile(
                type=unixfs.NodeType.File,
                layout="simple",
                metadata=unixfs.Metadata(mtime=mtime),
                content="mtime".encode()
            )
        )

        assert codec.decode(block) == unixfs.SimpleFile(
            type=unixfs.NodeType.File, layout="simple", metadata=unixfs.Metadata(mtime=mtime), content="mtime".encode()
        )
