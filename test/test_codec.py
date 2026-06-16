import pytest

from ipld_unixfs import codec, unixfs

from . import fixtures as blocks

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

    def test_mtime_without_nsecs(self):
        block = codec.encode(
            node=unixfs.SimpleFile(
                content="mtime".encode(),
                metadata=unixfs.Metadata(mtime=unixfs.MTime(secs=5, nsecs=0))
            )
        )

        assert codec.decode(block) == unixfs.SimpleFile(
            content="mtime".encode(), metadata=unixfs.Metadata(mtime=unixfs.MTime(secs=5, nsecs=0))
        )

    def test_does_not_overwrite_known_mode_bits(self):
        mode = 0xfffffff  # larger than currently defined mode bits

        block = codec.encode(
            node=unixfs.SimpleFile(
                content="bits".encode(), metadata=unixfs.Metadata(mode=mode)
            )
        )

        node = codec.decode(block)
        assert node, unixfs.SimpleFile(
            content="bits".encode(), metadata=unixfs.Metadata(mode=mode)
        )

    def test_empty(self):
        block = codec.encode(node=unixfs.SimpleFile(content=bytes()))

        expected = bytes([0x08, 0x02, 0x18, 0x00])
        assert block.tobytes()[2:] == expected

    def test_symlink(self):
        block = codec.encode(
            node=unixfs.Symlink(content="file.txt".encode())
        )

        assert codec.decode(block) == unixfs.Symlink(content="file.txt".encode(), metadata=unixfs.Metadata())

    def test_symlink_may_have_mode(self):
        block = codec.encode(
            node=unixfs.Symlink(
                content="file.txt".encode(),
                metadata=unixfs.Metadata(mode=0o664)
            )
        )

        assert codec.decode(block) == unixfs.Symlink(
            content="file.txt".encode(), metadata=unixfs.Metadata(mode=0o664)
        )

    def test_symlink_omit_default_mode(self):
        block = codec.encode(
            node=unixfs.Symlink(
                content="file.txt".encode(), metadata=unixfs.Metadata(mode=0o644)
            )
        )

        assert codec.decode(block) == unixfs.Symlink(
            content="file.txt".encode(), metadata=unixfs.Metadata()
        )

    def test_symlink_with_mtime_secs(self):
        block = codec.encode(
            node=unixfs.Symlink(
                content="file.txt".encode(),
                metadata=unixfs.Metadata(mtime=unixfs.MTime(secs=5))
            )
        )

        assert codec.decode(block) == unixfs.Symlink(
            content="file.txt".encode(),
            metadata=unixfs.Metadata(mtime=unixfs.MTime(secs=5, nsecs=0))
        )

    def test_symlink_with_mtime_nsecs(self):
        block = codec.encode(
            node=unixfs.Symlink(
                content="file.txt".encode(),
                metadata=unixfs.Metadata(mtime=unixfs.MTime(secs=5, nsecs=7))
            )
        )

        assert codec.decode(block) == unixfs.Symlink(
            content="file.txt".encode(),
            metadata=unixfs.Metadata(mtime=unixfs.MTime(secs=5, nsecs=7))
        )


class TestFormatNuances:
    def test_raw_with_no_content(self):
        encoded_bytes = codec.encode(codec.create_raw(content=bytes()))
        assert bytearray(encoded_bytes) == blocks.Qmdsf68UUYTSSx3i4GtDJfxzpAEZt7Mp23m3qa36LYMSiW

    def test_file_with_no_content(self):
        encoded_bytes = codec.encode_simple_file(content=bytes())
        assert encoded_bytes == blocks.QmbFMke1KXqnYyBBWxB74N4c5SBnJMVAiMNRcGu6x1AwQH

    def test_empty_flat_dir(self):
        encoded_bytes = codec.encode(codec.create_flat_directory(entries=[]))
        assert encoded_bytes == blocks.QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn

    def test_empty_sharded_dir(self):
        with pytest.raises(ValueError, match=".*power of two instead got 3"):
            codec.create_sharded_directory(
                entries=[], bitfield=bytes(), fanout=3, hash_type=0x22
            )

        with pytest.raises(ValueError, match=".*integer value instead got 0.2"):
            codec.create_sharded_directory(
                entries=[], bitfield=bytes(), fanout=16, hash_type=0.2
            )

        # note if you create a block like /ipfs/Qme1Cyu7ujqn3dRkRGmeTLpHJgbGHFjKmud48XK5W8qA6h
        # go-ipfs will say only murmur3 supported as hash function

        encoded_bytes = codec.encode(
            codec.create_sharded_directory(
                entries=[], bitfield=bytes(), fanout=256, hash_type=0x22
            )
        )
        assert encoded_bytes == blocks.Qma5kEnM5fEKTXrFC5zXYRy5QG3hcMWopoFS7ijhxx19qc

    def test_symlink(self):
        encoded_bytes = codec.encode(codec.create_symlink(path="hi".encode()))
        assert encoded_bytes == blocks.QmPZ1CTc5fYErTH2XXDGrfsPsHicYXtkZeVojGycwAfm3v
