"""Speaker consistency: ECAPA later. Mock store in-memory."""
_store: dict[str, list[float]] = {}


def enroll(speaker_id: str, embedding: list[float]) -> int:
    if embedding:
        _store[speaker_id] = embedding
        return len(embedding)
    _store.setdefault(speaker_id, [0.0] * 192)
    return 192


def match_score(speaker_id: str | None) -> float | None:
    if not speaker_id or speaker_id not in _store:
        return None
    # TODO: cosine vs live ECAPA embedding. Mock neutral.
    return 0.5
