def register_factory(factory_name: str):
    def wrapper(factory_class):
        factory_class.registered_factories[factory_name] = factory_class
        return factory_class
    return wrapper
