import os
import tempfile
import unittest
from pathlib import Path

from cosmos_mongo_compare.config import ConfigError, load_config


class LoadConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_files: list[str] = []
        self._saved_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._saved_env)
        for path in self._tmp_files:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def _write_tmp(self, content: str, suffix: str = ".yaml") -> str:
        f = tempfile.NamedTemporaryFile("w", delete=False, suffix=suffix, encoding="utf-8")
        try:
            f.write(content)
        finally:
            f.close()
        self._tmp_files.append(f.name)
        return f.name

    def test_allows_empty_collections_with_defaults(self) -> None:
        path = self._write_tmp(
            """
cosmos:
  api: mongo
  database: db1
  uri: "mongodb://example"
mongodb:
  uri: "mongodb://localhost:27017"
  database: db2
collections: {}
collection_defaults:
  enabled: true
  business_key: _id
sampling:
  percentage: 5
logging:
  main_log: "compare_summary.log"
  output_dir: "mismatch_logs"
""".lstrip()
        )
        cfg = load_config(path)
        self.assertEqual(cfg.collection_defaults.business_key, "_id")
        self.assertEqual(dict(cfg.collections), {})

    def test_rejects_non_mapping_collections(self) -> None:
        path = self._write_tmp(
            """
cosmos:
  api: mongo
  database: db1
  uri: "mongodb://example"
mongodb:
  uri: "mongodb://localhost:27017"
  database: db2
collections: []
sampling:
  percentage: 5
logging:
  main_log: "compare_summary.log"
  output_dir: "mismatch_logs"
""".lstrip()
        )
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_expands_env_vars_in_config_values(self) -> None:
        os.environ["COSMOS_URI"] = "mongodb://cosmos-env"
        os.environ["MONGODB_URI"] = "mongodb://mongo-env"
        path = self._write_tmp(
            """
cosmos:
  api: mongo
  database: db1
  uri: "${COSMOS_URI}"
mongodb:
  uri: "${MONGODB_URI}"
  database: db2
sampling:
  percentage: 5
logging:
  main_log: "compare_summary.log"
  output_dir: "mismatch_logs"
""".lstrip()
        )
        cfg = load_config(path)
        self.assertEqual(cfg.cosmos.uri, "mongodb://cosmos-env")
        self.assertEqual(cfg.mongodb.uri, "mongodb://mongo-env")

    def test_env_overrides_config_secrets(self) -> None:
        os.environ["MONGODB_URI"] = "mongodb://mongo-env"
        path = self._write_tmp(
            """
cosmos:
  api: mongo
  database: db1
  uri: "mongodb://cosmos-config"
mongodb:
  uri: "mongodb://mongo-config"
  database: db2
sampling:
  percentage: 5
logging:
  main_log: "compare_summary.log"
  output_dir: "mismatch_logs"
""".lstrip()
        )
        cfg = load_config(path)
        self.assertEqual(cfg.mongodb.uri, "mongodb://mongo-env")

    def test_parses_sampling_performance_controls(self) -> None:
        path = self._write_tmp(
            """
cosmos:
  api: sql
  database: db1
  endpoint: "https://example.documents.azure.com:443/"
  key: "k"
mongodb:
  uri: "mongodb://localhost:27017"
  database: db2
sampling:
  count: 500
  mode: bucket
  seed: 42
  deterministic_scan_log_every: 5000
  deterministic_max_scan_keys: 250000
  source_lookup_concurrency: 12
  compare_concurrency: 16
  compare_log_every: 2000
  bucket_field: sampleBucket
  bucket_modulus: 1024
  bucket_count: 12
  cosmos_retry_max_attempts: 9
  cosmos_retry_base_delay_ms: 750
logging:
  main_log: "compare_summary.log"
  output_dir: "mismatch_logs"
""".lstrip()
        )
        cfg = load_config(path)
        self.assertEqual(cfg.sampling.mode, "bucket")
        self.assertEqual(cfg.sampling.deterministic_scan_log_every, 5000)
        self.assertEqual(cfg.sampling.deterministic_max_scan_keys, 250000)
        self.assertEqual(cfg.sampling.source_lookup_concurrency, 12)
        self.assertEqual(cfg.sampling.compare_concurrency, 16)
        self.assertEqual(cfg.sampling.compare_log_every, 2000)
        self.assertEqual(cfg.sampling.bucket_field, "sampleBucket")
        self.assertEqual(cfg.sampling.bucket_modulus, 1024)
        self.assertEqual(cfg.sampling.bucket_count, 12)
        self.assertEqual(cfg.sampling.cosmos_retry_max_attempts, 9)
        self.assertEqual(cfg.sampling.cosmos_retry_base_delay_ms, 750)

    def test_rejects_bucket_mode_without_required_fields(self) -> None:
        path = self._write_tmp(
            """
cosmos:
  api: mongo
  database: db1
  uri: "mongodb://example"
mongodb:
  uri: "mongodb://localhost:27017"
  database: db2
sampling:
  count: 100
  mode: bucket
logging:
  main_log: "compare_summary.log"
  output_dir: "mismatch_logs"
""".lstrip()
        )
        with self.assertRaises(ConfigError):
            load_config(path)
