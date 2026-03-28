# tests/test_main_app.py
# Tests for main_app.py

import pytest
from main_app import calculate_division


class TestCalculateDivision:
    def test_normal_division(self):
        assert calculate_division(10, 2) == 5.0

    def test_integer_result(self):
        assert calculate_division(9, 3) == 3.0

    def test_float_result(self):
        assert calculate_division(1, 4) == 0.25

    def test_negative_numerator(self):
        assert calculate_division(-10, 2) == -5.0

    def test_negative_denominator(self):
        assert calculate_division(10, -2) == -5.0

    def test_both_negative(self):
        assert calculate_division(-10, -2) == 5.0

    def test_zero_numerator(self):
        assert calculate_division(0, 5) == 0.0

    def test_zero_denominator_raises(self):
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            calculate_division(10, 0)

    def test_zero_denominator_zero_numerator_raises(self):
        with pytest.raises(ZeroDivisionError):
            calculate_division(0, 0)

    def test_large_numbers(self):
        assert calculate_division(1_000_000, 1_000) == 1_000.0
