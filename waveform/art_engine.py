"""Mathematical drawing algorithms used by WAVEFORM."""
import math
import numpy as np

DEFAULTS = {
    "mode": "Parametric",
    "a": 5,
    "b": 8,
    "amplitude": 150,
    "rotation": 0,
    "color": "#A78BFA",
    "background": "#10111B",
    "line_width": 1.8,
}
MODES = ("Parametric", "Polar", "Spiral", "Lissajous")


def make_art(params):
    """Create x/y coordinate arrays for a selected mathematical curve."""
    mode = params.get("mode", "Parametric")
    t = np.linspace(0, 2 * np.pi, 3000)
    a = max(1, int(params.get("a", 5)))
    b = max(1, int(params.get("b", 8)))
    amp = float(params.get("amplitude", 150))
    phase = math.radians(float(params.get("rotation", 0)))

    if mode == "Parametric":
        x, y = amp * np.sin(a * t), amp * np.sin(b * t)
    elif mode == "Polar":
        r = amp * np.cos(a * t)
        x, y = r * np.cos(t), r * np.sin(t)
    elif mode == "Spiral":
        r = amp * t / (2 * np.pi)
        x, y = r * np.cos(a * t), r * np.sin(a * t)
    elif mode == "Lissajous":
        x, y = amp * np.sin(a * t + phase), amp * np.sin(b * t)
    else:
        raise ValueError("Unknown mathematical curve.")

    angle = math.radians(float(params.get("rotation", 0)))
    xr = x * np.cos(angle) - y * np.sin(angle)
    yr = x * np.sin(angle) + y * np.cos(angle)
    return xr, yr


def equation_text(params):
    mode = params.get("mode", "Parametric")
    a, b = int(params.get("a", 5)), int(params.get("b", 8))
    amp = int(float(params.get("amplitude", 150)))
    if mode == "Parametric":
        return f"x(t) = {amp} sin({a}t)\ny(t) = {amp} sin({b}t)"
    if mode == "Polar":
        return f"r(θ) = {amp} cos({a}θ)\nx = r cos(θ)\ny = r sin(θ)"
    if mode == "Spiral":
        return f"r(t) = {amp} × t / 2π\nx = r cos({a}t)\ny = r sin({a}t)"
    return f"x(t) = {amp} sin({a}t + φ)\ny(t) = {amp} sin({b}t)"


def _point_line_distance(point, start, end):
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    u = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (sx + u * dx), py - (sy + u * dy))


def simplify_rdp(points, epsilon=2.5):
    """Ramer-Douglas-Peucker point reduction."""
    points = [tuple(map(float, p)) for p in points]
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    distances = [_point_line_distance(p, start, end) for p in points[1:-1]]
    if not distances:
        return [start, end]
    max_distance = max(distances)
    index = distances.index(max_distance) + 1
    if max_distance > epsilon:
        left = simplify_rdp(points[:index + 1], epsilon)
        right = simplify_rdp(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def points_to_beziers(points):
    """Fit connected cubic Bézier segments using Catmull-Rom tangent estimates."""
    pts = [tuple(map(float, p)) for p in points]
    if len(pts) < 2:
        return []
    if len(pts) == 2:
        p0, p3 = pts
        dx, dy = (p3[0] - p0[0]) / 3, (p3[1] - p0[1]) / 3
        return [[p0, (p0[0] + dx, p0[1] + dy),
                 (p3[0] - dx, p3[1] - dy), p3]]
    segments = []
    for i in range(len(pts) - 1):
        p0, p3 = pts[i], pts[i + 1]
        prev = pts[i - 1] if i > 0 else p0
        nxt = pts[i + 2] if i + 2 < len(pts) else p3
        c1 = (p0[0] + (p3[0] - prev[0]) / 6,
              p0[1] + (p3[1] - prev[1]) / 6)
        c2 = (p3[0] - (nxt[0] - p0[0]) / 6,
              p3[1] - (nxt[1] - p0[1]) / 6)
        segments.append([p0, c1, c2, p3])
    return segments


def sample_bezier(segment, samples=24):
    p0, p1, p2, p3 = [np.array(p, dtype=float) for p in segment]
    t = np.linspace(0, 1, samples)
    pts = ((1-t)**3)[:, None] * p0 + (3*(1-t)**2*t)[:, None] * p1 + \
          (3*(1-t)*t**2)[:, None] * p2 + (t**3)[:, None] * p3
    return [tuple(p) for p in pts]


def validate_art_code(payload):
    """Validate .wave JSON data; imported files are data, never executable code."""
    if not isinstance(payload, dict) or payload.get("format") != "WAVEFORM_ART":
        raise ValueError("This is not a WAVEFORM art file.")
    if payload.get("version") != 1:
        raise ValueError("Unsupported WAVEFORM file version.")
    kind = payload.get("kind", "equation")
    if kind == "equation":
        params = payload.get("params")
        if not isinstance(params, dict):
            raise ValueError("Missing equation parameters.")
        clean = DEFAULTS.copy()
        clean.update({k: v for k, v in params.items() if k in clean})
        if clean["mode"] not in MODES:
            raise ValueError("Unknown curve type.")
        clean["a"] = max(1, min(20, int(clean["a"])))
        clean["b"] = max(1, min(20, int(clean["b"])))
        clean["amplitude"] = max(20, min(300, float(clean["amplitude"])))
        clean["rotation"] = max(0, min(360, float(clean["rotation"])))
        return {"kind": "equation", "params": clean}
    if kind == "freehand":
        strokes = payload.get("strokes")
        if not isinstance(strokes, list) or len(strokes) > 100:
            raise ValueError("Invalid freehand artwork.")
        cleaned = []
        for stroke in strokes:
            if not isinstance(stroke, dict):
                raise ValueError("Invalid stroke.")
            segments = stroke.get("segments")
            if not isinstance(segments, list) or len(segments) > 2000:
                raise ValueError("Invalid curve segments.")
            valid_segments = []
            for segment in segments:
                if not isinstance(segment, list) or len(segment) != 4:
                    raise ValueError("A Bézier segment needs four points.")
                points = []
                for point in segment:
                    if not isinstance(point, list) and not isinstance(point, tuple):
                        raise ValueError("Invalid Bézier point.")
                    if len(point) != 2:
                        raise ValueError("Invalid Bézier point.")
                    x, y = float(point[0]), float(point[1])
                    if not (-10000 <= x <= 10000 and -10000 <= y <= 10000):
                        raise ValueError("Point is outside allowed drawing area.")
                    points.append([x, y])
                valid_segments.append(points)
            color = str(stroke.get("color", "#A78BFA"))
            if len(color) != 7 or not color.startswith("#"):
                raise ValueError("Invalid stroke colour.")
            int(color[1:], 16)
            width = max(1, min(40, int(stroke.get("width", 4))))
            cleaned.append({"segments": valid_segments, "color": color, "width": width})
        return {"kind": "freehand", "strokes": cleaned}
    raise ValueError("Unknown artwork format.")
