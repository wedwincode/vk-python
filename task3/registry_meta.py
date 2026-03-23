class RegistryMeta(type):
    registry = {}

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)

        if name in mcls.registry:
            raise ValueError(f"class name '{name}' is already registered")

        mcls.registry[name] = cls
        return cls
