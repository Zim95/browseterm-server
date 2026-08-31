import unittest

from src.cloud.resource_quantity import InvalidQuantityError, parse_cpu_cores, parse_memory_bytes


class TestParseCpuCores(unittest.TestCase):
    def test_whole_core(self):
        self.assertEqual(parse_cpu_cores("1"), 1)
        self.assertEqual(parse_cpu_cores("4"), 4)

    def test_millicores_round_up(self):
        self.assertEqual(parse_cpu_cores("500m"), 1)
        self.assertEqual(parse_cpu_cores("2000m"), 2)
        self.assertEqual(parse_cpu_cores("2500m"), 3)

    def test_fractional_core_round_up(self):
        self.assertEqual(parse_cpu_cores("0.5"), 1)
        self.assertEqual(parse_cpu_cores("1.1"), 2)

    def test_invalid_raises(self):
        with self.assertRaises(InvalidQuantityError):
            parse_cpu_cores("not-a-number")
        with self.assertRaises(InvalidQuantityError):
            parse_cpu_cores("1Gi")


class TestParseMemoryBytes(unittest.TestCase):
    def test_binary_suffixes(self):
        self.assertEqual(parse_memory_bytes("2Gi"), 2 * 1024 ** 3)
        self.assertEqual(parse_memory_bytes("512Mi"), 512 * 1024 ** 2)
        self.assertEqual(parse_memory_bytes("1Ki"), 1024)

    def test_decimal_suffixes(self):
        self.assertEqual(parse_memory_bytes("1G"), 1_000_000_000)
        self.assertEqual(parse_memory_bytes("500M"), 500_000_000)

    def test_plain_bytes(self):
        self.assertEqual(parse_memory_bytes("1000000"), 1_000_000)

    def test_invalid_raises(self):
        with self.assertRaises(InvalidQuantityError):
            parse_memory_bytes("2Xi")
        with self.assertRaises(InvalidQuantityError):
            parse_memory_bytes("500m")


if __name__ == "__main__":
    unittest.main()
