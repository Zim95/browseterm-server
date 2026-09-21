from unittest import TestCase

from src.cloud.resource_quantity import derive_cpu_request_string, derive_memory_request_string


class TestDeriveCpuRequestString(TestCase):
    def test_whole_core_limit_with_ratio(self) -> None:
        self.assertEqual(derive_cpu_request_string("1", 0.1), "100m")

    def test_millicore_limit_with_ratio(self) -> None:
        self.assertEqual(derive_cpu_request_string("2000m", 0.5), "1")

    def test_rounds_down_to_millicores(self) -> None:
        self.assertEqual(derive_cpu_request_string("1", 0.15), "150m")


class TestDeriveMemoryRequestString(TestCase):
    def test_gi_limit_with_ratio_stays_gi(self) -> None:
        self.assertEqual(derive_memory_request_string("2Gi", 0.5), "1Gi")

    def test_gi_limit_with_ratio_rounds_to_mi(self) -> None:
        self.assertEqual(derive_memory_request_string("1Gi", 0.5), "512Mi")

    def test_mi_limit_with_ratio(self) -> None:
        self.assertEqual(derive_memory_request_string("512Mi", 0.5), "256Mi")
