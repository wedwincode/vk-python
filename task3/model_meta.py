from task3.registry_meta import RegistryMeta


class ModelMeta(RegistryMeta):
    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)

        fields = {}

        for base in bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)

        for attr_name, attr_value in namespace.items():
            if hasattr(attr_value, "__get__") and hasattr(attr_value, "__set__"):
                fields[attr_name] = attr_value

        cls._fields = fields
        return cls
