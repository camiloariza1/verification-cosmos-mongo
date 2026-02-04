from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable
from typing import Optional


class SourceClient(ABC):
    @abstractmethod
    def list_collections(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def count_documents(self, collection: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def sample_documents(self, *, collection: str, sample_size: int) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def iter_business_keys(self, *, collection: str, business_key: str) -> Iterable[Any]:
        raise NotImplementedError

    @abstractmethod
    def find_by_business_key(self, *, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        raise NotImplementedError
