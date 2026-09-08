def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Return sum of two numbers."""
    return a + b


if __name__ == "__main__":
    msg = greet("World")
    print(f"Message: {msg}")
    print("Sum:", add(5, 7))