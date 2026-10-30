import struct

import pytest

from app.stl_inspect import inspect_binary_stl


def test_inspect_binary_stl(tmp_path):
    path = tmp_path / "box.stl"
    header = b"test".ljust(80, b"\0") + struct.pack("<I", 1)
    triangle = struct.pack(
        "<12fH",
        0, 0, 1,
        -1, -2, 0,
        3, -2, 0,
        -1, 4, 5,
        0,
    )
    path.write_bytes(header + triangle)
    result = inspect_binary_stl(path)
    assert result == {"width": 4.0, "depth": 6.0, "height": 5.0, "triangles": 1}


def test_reject_noncanonical_stl(tmp_path):
    path = tmp_path / "bad.stl"
    path.write_bytes(b"solid fake")
    with pytest.raises(ValueError):
        inspect_binary_stl(path)

