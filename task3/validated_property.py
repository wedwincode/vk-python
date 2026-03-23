from task3.typed_property import TypedProperty


class ValidatedProperty(TypedProperty):
    def __init__(self, expected_type: type, min_value: int | None = None, max_value: int | None = None) -> None:
        super().__init__(expected_type)
        self._min_value = min_value
        self._max_value = max_value

    def __set__(self, instance, value):
        if self._min_value is not None and value < self._min_value:
            raise ValueError(f"attribute '{self._name}' must be greater than or equal to {self._min_value}")

        if self._max_value is not None and value > self._max_value:
            raise ValueError(f"attribute '{self._name}' must be less than or equal to {self._max_value}")

        super().__set__(instance, value)
