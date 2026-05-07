from abc import ABC, abstractmethod
from typing import Generic, TypeVar


DomainModel = TypeVar("DomainModel")
NewDomainModel = TypeVar("NewDomainModel")
UpdateDomainModel = TypeVar("UpdateDomainModel")


class AbstractCRUDRepository(ABC, Generic[DomainModel, NewDomainModel, UpdateDomainModel]):
    @abstractmethod
    def create(self, data: NewDomainModel) -> DomainModel:
        pass

    @abstractmethod
    def update(self, object_id: int, data: UpdateDomainModel) -> DomainModel:
        pass

    @abstractmethod
    def get(self) -> list[DomainModel]:
        pass

    @abstractmethod
    def delete(self, object_id: int) -> None:
        pass