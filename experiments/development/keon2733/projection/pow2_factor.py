from __future__ import annotations

def _pow2_factor(num: int) -> tuple[int, float]:
    """Factor num into 2^power * odd_part.

        Args:
            num: The integer to factor.

        Returns:
            A tuple (power, odd_part).
        """
    power = 0
    while num % 2 == 0:
        num /= 2
        power += 1
    return power, num
