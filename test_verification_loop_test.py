import unittest
from verification_loop_test import calculate_total

class TestCalculateTotal(unittest.TestCase):
    def test_calculate_total(self):
        self.assertEqual(calculate_total([1, 2, 3, 4]), 10)
        self.assertEqual(calculate_total([0, 0, 0]), 0)
        self.assertEqual(calculate_total([-1, 1]), 0)
        self.assertEqual(calculate_total([]), 0)

if __name__ == '__main__':
    unittest.main()