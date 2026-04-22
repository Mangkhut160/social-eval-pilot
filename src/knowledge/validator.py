from src.core.exceptions import KnowledgeError


def validate_weights(dimensions: list[dict]) -> None:
    total = sum(d["weight"] for d in dimensions)
    if abs(total - 1.0) > 0.01:
        raise KnowledgeError(f"维度权重之和必须为 1.0，当前值：{total:.4f}")
