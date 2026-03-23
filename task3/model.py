from task3.model_meta import ModelMeta
from task3.typed_property import TypedProperty


class Model(metaclass=ModelMeta):
    pass

class User(Model):
    age = TypedProperty(int)
    name = TypedProperty(str)
