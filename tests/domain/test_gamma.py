from domain.gamma import black_scholes_gamma


def test_black_scholes_gamma_returns_zero_for_invalid_input():
    assert black_scholes_gamma(0, 100, 0.2, 1.0) == 0.0
    assert black_scholes_gamma(100, 0, 0.2, 1.0) == 0.0
    assert black_scholes_gamma(100, 100, 0, 1.0) == 0.0
    assert black_scholes_gamma(100, 100, 0.2, 0) == 0.0


def test_black_scholes_gamma_returns_positive_value():
    gamma = black_scholes_gamma(100, 100, 0.2, 1.0)
    assert gamma > 0