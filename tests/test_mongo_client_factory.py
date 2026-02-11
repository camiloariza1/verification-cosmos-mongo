import os
import unittest

from cosmos_mongo_compare.clients.mongo_client_factory import build_mongo_client


class MongoClientFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._saved_env)

    def test_applies_timeout_env_vars_when_not_in_uri(self) -> None:
        os.environ["MONGODB_SERVER_SELECTION_TIMEOUT_MS"] = "3456"
        os.environ["MONGODB_CONNECT_TIMEOUT_MS"] = "1234"
        os.environ["MONGODB_SOCKET_TIMEOUT_MS"] = "2345"
        client = build_mongo_client("mongodb://localhost:27017/?connect=false")

        self.assertAlmostEqual(client.options.server_selection_timeout, 3.456, places=3)
        self.assertAlmostEqual(client._topology_settings.pool_options.connect_timeout, 1.234, places=3)
        self.assertAlmostEqual(client._topology_settings.pool_options.socket_timeout, 2.345, places=3)

    def test_does_not_override_uri_timeouts(self) -> None:
        os.environ["MONGODB_SERVER_SELECTION_TIMEOUT_MS"] = "9999"
        client = build_mongo_client("mongodb://localhost:27017/?connect=false&serverSelectionTimeoutMS=1111")
        self.assertAlmostEqual(client.options.server_selection_timeout, 1.111, places=3)

