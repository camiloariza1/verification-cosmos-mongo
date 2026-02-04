import unittest

from cosmos_mongo_compare.compare import compare_documents


class CompareDocumentsTests(unittest.TestCase):
    def test_exclude_fields_anywhere(self):
        a = {"_id": 1, "x": {"_id": 2, "v": 1}}
        b = {"_id": 9, "x": {"_id": 10, "v": 1}}
        diffs = compare_documents(a, b, exclude_fields=["_id"])
        self.assertEqual(diffs, [])

    def test_exclude_fields_dotted_path(self):
        a = {"meta": {"etag": "a", "v": 1}}
        b = {"meta": {"etag": "b", "v": 1}}
        diffs = compare_documents(a, b, exclude_fields=["meta.etag"])
        self.assertEqual(diffs, [])

    def test_value_mismatch_with_path(self):
        a = {"a": {"b": 1}}
        b = {"a": {"b": 2}}
        diffs = compare_documents(a, b)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].path, "a.b")
        self.assertEqual(diffs[0].kind, "value_mismatch")

    def test_array_order_insensitive(self):
        a = {"tags": [1, 2, 2]}
        b = {"tags": [2, 1, 2]}
        diffs = compare_documents(a, b, array_order_insensitive_paths=["tags"])
        self.assertEqual(diffs, [])


if __name__ == "__main__":
    unittest.main()

