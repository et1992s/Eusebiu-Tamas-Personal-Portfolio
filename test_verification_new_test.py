import unittest
from verification_new_test import calculate_total

class TestCalculateTotal(unittest.TestCase):
    def test_calculate_total(self):
        self.assertEqual(calculate_total([1, 2, 3, 4]), 10)
        self.assertEqual(calculate_total([1, 2, 3, 4, 5]), 15)
        self.assertEqual(calculate_total([]), 0)
        self.assertEqual(calculate_total([-1, -2, -3, -4]), -10)

if __name__ == '__main__':
    unittest.main()