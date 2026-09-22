from viperf3.widgets import _bresenham, _rasterize, _DOT_BITS


def test_bresenham_endpoints():
    pts = list(_bresenham(0, 0, 5, 3))
    assert pts[0] == (0, 0)
    assert pts[-1] == (5, 3)
    # continuous: neighbouring points differ by at most 1 in each axis
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        assert abs(x1 - x0) <= 1 and abs(y1 - y0) <= 1


def test_rasterize_single_point():
    grid = _rasterize([1.0], [5.0], 0.0, 2.0, 0.0, 10.0, 20, 16)
    assert len(grid) == 1


def test_rasterize_line_spans_width():
    # A horizontal line across the full x-range must touch first & last columns
    grid = _rasterize([0.0, 10.0], [5.0, 5.0], 0.0, 10.0, 0.0, 10.0, 40, 16)
    cols = {cell[0] for cell in grid}
    assert 0 in cols
    assert 19 in cols  # 40 subpixels / 2 per cell = 20 columns


def test_rasterize_merging_cells_have_valid_bits():
    grid = _rasterize([0.0, 1.0, 2.0], [0.0, 10.0, 0.0], 0.0, 2.0, 0.0, 10.0, 20, 16)
    valid = {bit for row in _DOT_BITS for bit in row}
    for bits in grid.values():
        assert 0 < bits <= 0xFF
        # bits must be a union of valid dot bits
        rest = bits
        for b in sorted(valid, reverse=True):
            if rest & b:
                rest &= ~b
        assert rest == 0
