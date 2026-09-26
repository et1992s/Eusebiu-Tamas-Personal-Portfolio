import unittest
from verification_test import calculate_total

class TestCalculateTotal(unittest.TestCase):
    def test_calculate_total(self):
        self.assertEqual(calculate_total([1, 2, 3]), 6)
        self.assertEqual(calculate_total([-1, 1, 0]), 0)
        self.assertEqual(calculate_total([]), 0)
        self.assertEqual(calculate_total([10, 20, 30]), 60)

if __name__ == '__main__':
    unittest.main()
