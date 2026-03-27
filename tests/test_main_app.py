# tests/test_main_app.py

import pytest
from main_app import calculate_division


class TestCalculateDivision:
    def test_normal_division(self):
        assert calculate_division(10, 2) == 5.0

    def test_integer_division_returns_float(self):
        assert calculate_division(7, 2) == 3.5

    def test_negative_numerator(self):
        assert calculate_division(-10, 2) == -5.0

    def test_negative_denominator(self):
        assert calculate_division(10, -2) == -5.0

    def test_both_negative(self):
        assert calculate_division(-10, -2) == 5.0

    def test_zero_numerator(self):
        assert calculate_division(0, 5) == 0.0

    def test_divide_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            calculate_division(10, 0)

    def test_float_arguments(self):
        assert calculate_division(1.5, 0.5) == 3.0

    def test_large_numbers(self):
        result = calculate_division(10**9, 10**3)
        assert result == 10**6
