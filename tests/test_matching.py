import unittest

import colour
import numpy as np

from color_matching import load_library, match_rgb, rgb_to_lab, sample_region, validate_library
from generate_demo_library import generate_rows


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library()

    def test_exact_reference_matches_itself(self):
        for _, row in self.library.iterrows():
            with self.subTest(name=row.ReferenceName):
                result = match_rgb(row[["R", "G", "B"]].to_numpy(dtype=float), self.library)
                self.assertEqual(result["name"], row.ReferenceName)
                self.assertLess(result["delta_e"], 1e-7)

    def test_black_white_and_invalid_rgb(self):
        self.assertAlmostEqual(rgb_to_lab([0, 0, 0])[0], 0, places=5)
        self.assertAlmostEqual(rgb_to_lab([255, 255, 255])[0], 100, places=4)
        for rgb in ([256, 0, 0], [-1, 0, 0], [1, 2], [np.nan, 0, 0]):
            with self.subTest(rgb=rgb), self.assertRaises(ValueError):
                rgb_to_lab(rgb)

    def test_ciede2000_known_reference_pair(self):
        # Published CIEDE2000 supplementary test pair, expected rounded result.
        distance = colour.delta_E([50, 2.6772, -79.7751], [50, 0, -82.7485], method="CIE 2000")
        self.assertAlmostEqual(float(distance), 2.0425, places=4)

    def test_library_rejects_invalid_values_and_names(self):
        bad_frames = [self.library.iloc[:0], self.library.drop(columns="R")]
        for column, value in (("L_val", np.inf), ("R", 256), ("R", 1.5),
                              ("L_val", -1), ("ReferenceName", "")):
            frame = self.library.copy()
            if isinstance(value, float):
                frame[column] = frame[column].astype(float)
            frame.loc[0, column] = value
            bad_frames.append(frame)
        duplicate = self.library.copy()
        duplicate.loc[1, "ReferenceName"] = duplicate.loc[0, "ReferenceName"]
        bad_frames.append(duplicate)
        for frame in bad_frames:
            with self.subTest(frame=frame.shape), self.assertRaises(ValueError):
                validate_library(frame)

    def test_bgr_sampling_and_edges(self):
        frame = np.zeros((5, 5, 3), dtype=np.uint8)
        frame[:, :] = [10, 20, 30]
        self.assertEqual(sample_region(frame, 0, 0), (30, 20, 10))
        frame[2, 2] = [110, 120, 130]
        np.testing.assert_allclose(sample_region(frame, 2, 2), [34, 24, 14])
        with self.assertRaises(ValueError):
            sample_region(frame, -1, 0)
        with self.assertRaises(ValueError):
            sample_region(frame, 0, 0, size=2)

    def test_generator_matches_committed_synthetic_data(self):
        rows = generate_rows()
        self.assertEqual(len(rows), 56)
        self.assertEqual([row[0] for row in rows], list(self.library.ReferenceName))
        np.testing.assert_allclose(
            np.array([row[1:] for row in rows], dtype=float),
            self.library.iloc[:, 1:].to_numpy(dtype=float), atol=1e-8)


if __name__ == "__main__":
    unittest.main()
