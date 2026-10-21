def nonnegative_int(value, max_value=1000):
    x = int(value)
    if not 0 <= x <= max_value:
        raise ValueError("Value outside allowed range")
    return x
