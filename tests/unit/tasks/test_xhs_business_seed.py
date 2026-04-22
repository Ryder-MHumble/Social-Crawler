from __future__ import annotations

from tasks.xhs_business_seed.keyword_config import (
    build_keyword_pool,
    split_keywords_into_batches,
)


def test_keyword_batches_cover_pool_without_duplicates() -> None:
    keywords = build_keyword_pool(include_core=True, include_scene=True, include_risk=False)
    batches = split_keywords_into_batches(keywords, parallel_jobs=4)

    flattened = [keyword for batch in batches for keyword in batch]

    assert len(batches) == 4
    assert flattened == keywords
    assert len(flattened) == len(set(flattened))

