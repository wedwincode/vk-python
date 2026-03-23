class TypedProperty:
    def __init__(self, expected_type: type) -> None:
        self._expected_type = expected_type

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self._name not in instance.__dict__:
            raise AttributeError(f"attribute '{self._name}' is not set")
        return instance.__dict__[self._name]

    def __set__(self, instance, value):
        if not isinstance(value, self._expected_type):
            raise TypeError(f"attribute '{self._name}' must be of type {self._expected_type.__name__}, "
                            f"got {type(value).__name__}")
        instance.__dict__[self._name] = value
