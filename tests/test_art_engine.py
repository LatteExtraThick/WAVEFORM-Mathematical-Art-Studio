import unittest
from waveform.art_engine import (
    DEFAULTS, MODES, make_art, equation_text, simplify_rdp,
    points_to_beziers, sample_bezier, validate_art_code
)


class WaveformTests(unittest.TestCase):
    def test_equation_modes(self):
        for mode in MODES:
            params = DEFAULTS.copy()
            params["mode"] = mode
            x, y = make_art(params)
            self.assertEqual(len(x), len(y))
            self.assertGreater(len(x), 100)

    def test_equation_explanation(self):
        self.assertIn("sin", equation_text(DEFAULTS))

    def test_rdp_reduces_straight_line_points(self):
        points = [(i, i * 2) for i in range(100)]
        reduced = simplify_rdp(points, 1.0)
        self.assertEqual(len(reduced), 2)

    def test_bezier_segments_and_sampling(self):
        points = [(0, 0), (10, 10), (20, 0), (30, 10)]
        segments = points_to_beziers(points)
        self.assertEqual(len(segments), 3)
        sampled = sample_bezier(segments[0])
        self.assertEqual(sampled[0], (0.0, 0.0))
        self.assertEqual(sampled[-1], (10.0, 10.0))

    def test_freehand_share_validation(self):
        payload = {
            "format": "WAVEFORM_ART", "version": 1, "kind": "freehand",
            "strokes": [{"segments": [[[0, 0], [1, 1], [2, 1], [3, 0]]],
                         "color": "#A78BFA", "width": 4}]
        }
        result = validate_art_code(payload)
        self.assertEqual(result["kind"], "freehand")
        self.assertEqual(len(result["strokes"]), 1)

    def test_reject_unknown_art_file(self):
        with self.assertRaises(ValueError):
            validate_art_code({"format": "OTHER", "version": 1})


if __name__ == "__main__":
    unittest.main()
