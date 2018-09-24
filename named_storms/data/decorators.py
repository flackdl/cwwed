def register_factory(factory_name: str):
    def wrapper(factory_class):
        # import locally to prevent circular dependencies
        from named_storms.data.factory import ProcessorBaseFactory
        ProcessorBaseFactory.registered_factories[factory_name] = factory_class
        return factory_class
    return wrapper
