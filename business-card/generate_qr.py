"""Generate a dependency-free QR SVG for the public course information page."""

from pathlib import Path

URL = "https://olgatkach1989.github.io/Hefner_Sprach_Hub/angebot/"
VERSION = 4
DATA_CODEWORDS = 80
ECC_CODEWORDS = 20
MASK = 0


def gf_mul(left: int, right: int) -> int:
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
    return result


def rs_remainder(data: list[int], degree: int) -> list[int]:
    generator = [1]
    root = 1
    for _ in range(degree):
        next_poly = [0] * (len(generator) + 1)
        for index, coefficient in enumerate(generator):
            next_poly[index] ^= coefficient
            next_poly[index + 1] ^= gf_mul(coefficient, root)
        generator = next_poly
        root = gf_mul(root, 2)

    remainder = data + [0] * degree
    for index in range(len(data)):
        factor = remainder[index]
        if factor:
            for offset, coefficient in enumerate(generator):
                remainder[index + offset] ^= gf_mul(coefficient, factor)
    return remainder[-degree:]


def bch_remainder(value: int, polynomial: int) -> int:
    value <<= polynomial.bit_length() - 1
    while value.bit_length() >= polynomial.bit_length():
        value ^= polynomial << (value.bit_length() - polynomial.bit_length())
    return value


def make_matrix() -> list[list[bool]]:
    size = VERSION * 4 + 17
    matrix: list[list[bool | None]] = [[None] * size for _ in range(size)]

    def put(x: int, y: int, value: bool) -> None:
        if 0 <= x < size and 0 <= y < size:
            matrix[y][x] = value

    def finder(left: int, top: int) -> None:
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                x, y = left + dx, top + dy
                if 0 <= x < size and 0 <= y < size:
                    inside = 0 <= dx <= 6 and 0 <= dy <= 6
                    dark = inside and (
                        dx in (0, 6) or dy in (0, 6)
                        or (2 <= dx <= 4 and 2 <= dy <= 4)
                    )
                    put(x, y, dark)

    finder(0, 0)
    finder(size - 7, 0)
    finder(0, size - 7)

    # Version 4 has one alignment pattern at (26, 26).
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            put(26 + dx, 26 + dy, max(abs(dx), abs(dy)) != 1)

    for index in range(8, size - 8):
        put(index, 6, index % 2 == 0)
        put(6, index, index % 2 == 0)

    # Reserve both format-information areas and the fixed dark module.
    for index in range(6):
        put(8, index, False)
    put(8, 7, False)
    put(8, 8, False)
    put(7, 8, False)
    for index in range(9, 15):
        put(14 - index, 8, False)
    for index in range(8):
        put(size - 1 - index, 8, False)
    for index in range(8, 15):
        put(8, size - 15 + index, False)
    put(8, size - 8, True)

    # Byte mode, error-correction level L, mask 0.
    format_data = (0b01 << 3) | MASK
    format_bits = ((format_data << 10) | bch_remainder(format_data, 0x537)) ^ 0x5412
    for index in range(6):
        put(8, index, bool((format_bits >> index) & 1))
    put(8, 7, bool((format_bits >> 6) & 1))
    put(8, 8, bool((format_bits >> 7) & 1))
    put(7, 8, bool((format_bits >> 8) & 1))
    for index in range(9, 15):
        put(14 - index, 8, bool((format_bits >> index) & 1))
    for index in range(8):
        put(size - 1 - index, 8, bool((format_bits >> index) & 1))
    for index in range(8, 15):
        put(8, size - 15 + index, bool((format_bits >> index) & 1))
    put(8, size - 8, True)

    payload = URL.encode("utf-8")
    bits = [0, 1, 0, 0]
    bits.extend((len(payload) >> shift) & 1 for shift in range(7, -1, -1))
    for byte in payload:
        bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
    capacity = DATA_CODEWORDS * 8
    if len(bits) > capacity:
        raise ValueError("URL does not fit the selected QR version")
    bits.extend([0] * min(4, capacity - len(bits)))
    bits.extend([0] * ((-len(bits)) % 8))

    data = [sum(bits[offset + bit] << (7 - bit) for bit in range(8))
            for offset in range(0, len(bits), 8)]
    pads = (0xEC, 0x11)
    while len(data) < DATA_CODEWORDS:
        data.append(pads[(len(data) - ((len(bits) + 7) // 8)) % 2])
    codewords = data + rs_remainder(data, ECC_CODEWORDS)
    stream = [((word >> shift) & 1) for word in codewords for shift in range(7, -1, -1)]

    bit_index = 0
    upward = True
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vertical in range(size):
            y = size - 1 - vertical if upward else vertical
            for offset in range(2):
                x = right - offset
                if matrix[y][x] is None:
                    value = bool(stream[bit_index]) if bit_index < len(stream) else False
                    bit_index += 1
                    if (x + y) % 2 == 0:
                        value = not value
                    matrix[y][x] = value
        upward = not upward
        right -= 2

    if bit_index < len(stream):
        raise ValueError("QR matrix did not contain enough data modules")
    return [[bool(cell) for cell in row] for row in matrix]


def write_svg(matrix: list[list[bool]]) -> None:
    size = len(matrix)
    quiet_zone = 4
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-4 -4 41 41" ',
        'width="410" height="410" shape-rendering="crispEdges">',
        '<title>QR code to Hefner Sprach Hub course information</title>',
        '<rect x="-4" y="-4" width="41" height="41" fill="#fff"/>',
        '<path fill="#000" d="',
    ]
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                parts.append(f"M{x} {y}h1v1h-1z")
    parts.append('"/></svg>')
    Path(__file__).with_name("qr.svg").write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    write_svg(make_matrix())
