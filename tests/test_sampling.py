import logging
import unittest
from typing import Any, Iterable, Optional

from cosmos_mongo_compare.clients.base import SourceClient
from cosmos_mongo_compare.sampling import sample_source_documents


class FakeSource(SourceClient):
    def __init__(self, docs: list[dict]):
        self._docs = docs
        self.sample_documents_calls = 0
        self.iter_business_keys_calls = 0
        self.sample_by_bucket_calls = 0

    def list_collections(self) -> list[str]:
        return ["c"]

    def count_documents(self, collection: str) -> int:
        return len(self._docs)

    def sample_documents(self, *, collection: str, sample_size: int) -> list[dict]:
        self.sample_documents_calls += 1
        return self._docs[:sample_size]

    def iter_business_keys(self, *, collection: str, business_key: str) -> Iterable[Any]:
        self.iter_business_keys_calls += 1
        for doc in self._docs:
            yield doc.get(business_key)

    def find_by_business_key(self, *, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        for doc in self._docs:
            if doc.get(business_key) == key_value:
                return doc
        return None

    def sample_documents_by_buckets(
        self,
        *,
        collection: str,
        bucket_field: str,
        bucket_values: list[int],
        sample_size: int,
    ) -> list[dict]:
        self.sample_by_bucket_calls += 1
        selected = [d for d in self._docs if d.get(bucket_field) in set(bucket_values)]
        return selected[:sample_size]


class SamplingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("sampling-tests")

    def test_fast_mode_uses_source_sampling(self) -> None:
        source = FakeSource([{"id": i} for i in range(10)])
        docs = sample_source_documents(
            source=source,
            collection="c",
            business_key="id",
            sample_size=3,
            seed=None,
            mode="fast",
            source_total=10,
            source_lookup_concurrency=4,
            deterministic_scan_log_every=1000,
            deterministic_max_scan_keys=None,
            bucket_field=None,
            bucket_modulus=None,
            bucket_count=8,
            logger=self.logger,
        )
        self.assertEqual(len(docs), 3)
        self.assertEqual(source.sample_documents_calls, 1)
        self.assertEqual(source.iter_business_keys_calls, 0)

    def test_deterministic_mode_respects_scan_cap(self) -> None:
        source = FakeSource([{"id": i} for i in range(1, 1001)])
        docs = sample_source_documents(
            source=source,
            collection="c",
            business_key="id",
            sample_size=20,
            seed=7,
            mode="deterministic",
            source_total=1000,
            source_lookup_concurrency=2,
            deterministic_scan_log_every=200,
            deterministic_max_scan_keys=100,
            bucket_field=None,
            bucket_modulus=None,
            bucket_count=8,
            logger=self.logger,
        )
        self.assertTrue(all(1 <= d["id"] <= 100 for d in docs))
        self.assertEqual(source.iter_business_keys_calls, 1)

    def test_bucket_mode_uses_bucket_sampling(self) -> None:
        source = FakeSource([{"id": i, "sampleBucket": i % 16} for i in range(1, 501)])
        docs = sample_source_documents(
            source=source,
            collection="c",
            business_key="id",
            sample_size=25,
            seed=42,
            mode="bucket",
            source_total=500,
            source_lookup_concurrency=4,
            deterministic_scan_log_every=200,
            deterministic_max_scan_keys=None,
            bucket_field="sampleBucket",
            bucket_modulus=16,
            bucket_count=2,
            logger=self.logger,
        )
        self.assertTrue(docs)
        self.assertLessEqual(len(docs), 25)
        self.assertGreater(source.sample_by_bucket_calls, 0)


if __name__ == "__main__":
    unittest.main()
