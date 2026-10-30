from __future__ import annotations

import struct
from pathlib import Path


def inspect_binary_stl(path: Path) -> dict[str, float | int]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("STL is too short")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError("only canonical binary STL is accepted")
    low = [float("inf")] * 3
    high = [float("-inf")] * 3
    for face in range(count):
        offset = 84 + 50 * face + 12
        values = struct.unpack_from("<9f", data, offset)
        for i in range(0, 9, 3):
            for axis in range(3):
                value = values[i + axis]
                low[axis] = min(low[axis], value)
                high[axis] = max(high[axis], value)
    return {
        "width": high[0] - low[0],
        "depth": high[1] - low[1],
        "height": high[2] - low[2],
        "triangles": count,
    }

