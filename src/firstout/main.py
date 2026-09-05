"""프로그램 진입점."""

from __future__ import annotations


def greet(name: str = "world") -> str:
    """인사말을 만들어 돌려준다."""
    return f"Hello, {name}!"


def main() -> None:
    print(greet())


if __name__ == "__main__":
    main()
