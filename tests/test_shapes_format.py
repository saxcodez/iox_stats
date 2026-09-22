from PySide6.QtCore import QPointF, QRectF

from iox_stats.collectors import split_bytes, split_rate, uptime_parts
from iox_stats.ui.shapes import smooth_path, squircle_path


def test_squircle_fits_rect_and_is_closed(qapp):
    r = QRectF(10, 20, 158, 158)
    path = squircle_path(r, 22)
    bb = path.boundingRect()
    assert abs(bb.left() - r.left()) < 0.5 and abs(bb.right() - r.right()) < 0.5
    assert abs(bb.top() - r.top()) < 0.5 and abs(bb.bottom() - r.bottom()) < 0.5
    assert path.contains(r.center())
    assert not path.contains(QPointF(r.left() + 1, r.top() + 1))      # the corner is cut
    assert path.contains(QPointF(r.center().x(), r.top() + 1))        # the edge middle is not


def test_squircle_degenerate_radius_is_plain_rect(qapp):
    path = squircle_path(QRectF(0, 0, 40, 40), 0)
    assert path.contains(QPointF(1, 1))


def test_smooth_path_passes_through_points_and_clamps(qapp):
    pts = [QPointF(0, 10), QPointF(10, 0), QPointF(20, 10), QPointF(30, 0)]
    path = smooth_path(pts, floor_y=10, ceil_y=0)
    ys = [path.elementAt(i).y for i in range(path.elementCount())]
    assert min(ys) >= -1e-6 and max(ys) <= 10 + 1e-6
    assert path.elementAt(0).x == 0 and path.currentPosition().x() == 30


def test_split_helpers():
    assert split_bytes(180 * 1024**3) == ("180", "GB")
    assert split_bytes(1536) == ("1.5", "KB")
    assert split_rate(2.5 * 1024**2) == ("2.5", "MB/s")
    assert uptime_parts(3 * 86400 + 5 * 3600) == [("3", "d"), ("5", "h")]
    assert uptime_parts(5 * 3600 + 7 * 60) == [("5", "h"), ("7", "m")]
    assert uptime_parts(90) == [("1", "m")]
