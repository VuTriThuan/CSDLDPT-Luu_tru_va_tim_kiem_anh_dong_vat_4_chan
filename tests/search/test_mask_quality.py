import unittest
from unittest import mock

import cv2
import numpy as np

from tools.search.mask_quality import analyze_mask, review_message
from tools.search.query import create_mask, refine


class MaskQualityTests(unittest.TestCase):
    def test_remote_single_pixel_exposes_bbox_inflation_without_removing_it(self):
        mask = np.zeros((100, 200), np.uint8)
        mask[30:70, 60:140] = 255
        mask[95, 190] = 255
        before = mask.copy()
        report = analyze_mask(mask)
        self.assertIn('tiny_components_expand_bbox', report['review_flags'])
        self.assertEqual(report['substantial_component_bbox'], [60, 30, 80, 40])
        self.assertGreater(report['bbox_area_inflation_from_tiny_components'], 2)
        np.testing.assert_array_equal(mask, before)

    def test_initial_bbox_border_uses_actual_rectangle(self):
        mask = np.zeros((100, 200), np.uint8)
        mask[30:70, 60:140] = 255
        report = analyze_mask(mask, (60, 30, 80, 40))
        self.assertEqual(report['initial_bbox_border_fraction'], 1.)
        self.assertIn('near_initial_bbox_border', report['review_flags'])
        broad = analyze_mask(mask, (10, 10, 180, 80))
        self.assertEqual(broad['initial_bbox_border_fraction'], 0.)

    def test_no_flags_is_not_a_segmentation_accuracy_claim(self):
        mask = np.zeros((100, 200), np.uint8); mask[30:70, 60:140] = 255
        report = analyze_mask(mask)
        self.assertEqual(report['review_flags'], [])
        self.assertIn('does not certify', report['interpretation'])
        self.assertIn('không xác nhận', review_message(report))

    def test_unpainted_refine_is_rejected_without_running_grabcut(self):
        rgb = np.zeros((80, 120, 3), np.uint8)
        mask = np.zeros((80, 120), np.uint8); mask[20:60, 30:90] = 255
        with mock.patch('cv2.grabCut') as gc:
            with self.assertRaisesRegex(ValueError, 'No keep/remove strokes'):
                refine(rgb, mask, np.full(mask.shape, 255, np.uint8))
        gc.assert_not_called()

    def test_user_rectangle_preserves_grabcut_thin_parts(self):
        rgb = np.zeros((80, 120, 3), np.uint8)
        expected = np.zeros((80, 120), np.uint8)
        expected[20:45, 30:90] = 255
        expected[45:65, 38:40] = 255
        expected[45:65, 80:82] = 255
        def gc(image, labels, rect, *args):
            labels[expected > 0] = cv2.GC_FGD
        with mock.patch('cv2.grabCut', side_effect=gc), mock.patch('cv2.morphologyEx') as morph:
            result, info = create_mask(rgb, (10, 10, 100, 60))
        np.testing.assert_array_equal(result, expected)
        morph.assert_not_called()
        self.assertEqual(info['morphology'], 'none')
        self.assertFalse(info['automatic_bbox'])


if __name__ == '__main__':
    unittest.main()
