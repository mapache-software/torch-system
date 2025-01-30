from re import sub
from typing import Callable
from typing import Any
from typing import Union
from inspect import signature

from torchsystem.depends import inject, Provider
from torchsystem.depends import Depends as Depends

class Consumer:    
    """
    A CONSUMER is a component that listens for and reacts to ocurrences in a BOUNDED CONTEXT. Occurrences
    can be modeled as events and should contain all the information needed to describe what happened in
    the system. Then CONSUMERs are responsible for processing events and triggering side effects in response
    to them.

    Unlike a SUBSCRIBER, that receive messages routed by the PUBLISHER, a CONSUMER is responsible
    for deciding which handlers to invoke based on the type of the message it consumes. The message type should
    describe the ocurrence in past tense as DDD suggests when modeling events.

    Methods:
        register:
            Registers a message type and its corresponding handler function.

        handler:
            Decorator for registering a handler function for one or more message types.

        consume:
            Consumes a message by invoking its registered handler functions.
            
    Example:
        ```python	
        from torchsystem.services import Consumer
        from torchsystem.services import Publisher

        class Event:...

        @dataclass
        class ModelTrained(Event):
            model: Callable
            metrics: Sequence

        @dataclass
        class ModelEvaluated(Event):
            model: Callable
            metrics: Sequence

        consumer = Consumer()
        publisher = Publisher()

        @consumer.handler
        def on_model_iterated(event: UserCreated | UserUpdated):
            for metric in event.metrics:
                publisher.publish(metric, metric['name'])

        consumer.consume(ModelTrained(model, [{'name': 'loss', 'value': 0.1}, {'name': 'accuracy', 'value': 0.9}]))
        consumer.consume(ModelEvaluated(model, [{'name': 'loss', 'value': 0.1}, {'name': 'accuracy', 'value': 0.9}]))
        ```
    """
    def __init__(
        self, 
        name: str = None,
        *,
        generator: Callable[[str], str] = lambda name: sub(r'(?<!^)(?=[A-Z])', '-', name).lower(),
        provider: Provider = None
    ):
        self.name = name
        self.handlers = dict[str, list[Callable[[Any], None]]]()
        self.types = dict[str, Any]()
        self.generator = generator
        self.provider = provider or Provider()

    @property
    def dependency_overrides(self) -> dict:
        """
        Returns the dependency overrides for the consumer. This is useful for late binding, 
        testing and changing the behavior of the consumer in runtime.

        Returns:
            dict: A dictionary of the dependency map.
        """
        return self.provider.dependency_overrides

    def register(self, annotation: Any, handler: Callable[..., None]) -> Callable[..., None]:
        """
        Registers a message type and its corresponding handler function. Handles nested or generic annotations
        and union types. If the annotation is a union type, it will register the handler for each of its arguments.

        This method is used to register a handler from the `handler` method and should not be called directly. Use
        the `handler` decorator instead.

        Args:
            annotation (Any): The message annotation to be registered.
            handler (Callable[..., None]): The handler function to be registered.

        Returns:
            Callable[..., None]: The injected handler function.
        """
        if hasattr(annotation, '__origin__'):
            origin = getattr(annotation, '__origin__')
            if isinstance(origin, type(Union)):
                for arg in getattr(annotation, '__args__'):
                    self.register(arg if not hasattr(arg, '__origin__') else getattr(arg, '__origin__'), handler)
            else:
                self.register(origin, handler)

        elif hasattr(annotation, '__args__'):
            for arg in getattr(annotation, '__args__'):
                self.register(arg if not hasattr(arg, '__origin__') else getattr(arg, '__origin__'), handler)
        else:
            key = self.generator(annotation.__name__)
            self.types[key] = annotation    
            injected = inject(self.provider)(handler)
            self.handlers.setdefault(key, []).append(injected)
            return injected

    def handler(self, wrapped: Callable[..., None]) -> Callable[..., None]:
        """
        Decorator for registering a handler function for one or more message types. The handler is registered
        with the name of the function as the key. The handler is also injected with the dependencies provided by
        the consumer.

        Each message type can have multiple handlers registered to it and each handler can be registered to multiple
        message at the same time using unions. 

        Args:
            wrapped (Callable[..., None]): The function to be registered as a handler.

        Returns:
            Callable[..., None]: The injected handler function.
        """
        function_signature = signature(wrapped)
        parameter = next(iter(function_signature.parameters.values()))
        injected = self.register(parameter.annotation, wrapped)
        return injected

    def consume(self, message: Any):
        """
        Consumes a message by invoking its registered handler functions. If the message type is not registered
        with any handler, it will be ignored.

        Args:
            message (Any): The message to consume.
        """
        key = self.generator(message.__class__.__name__)
        for handler in self.handlers.get(key, []):
            handler(message)

class Producer:
    """
    A producer is responsible for
    emitting EVENTS that are consumed by consumers. You can implement a producer implementing the `register`
    method to register consumers, and some delivery mechanism to deliver the events to them.

    Methods:
        register: Registers a consumer to the producer.
        dispatch: Dispatches an event to all registered consumers.
    
    Example:
        ```python	
        from torchsystem.services import Consumer
        from torchsystem.services import Producer

        class Event:...

        @dataclass
        class ModelTrained(Event):
            model: Callable
            metrics: Sequence

        @dataclass
        class ModelEvaluated(Event):
            model: Callable
            metrics: Sequence

        ...

        producer = Producer()
        producer.register(consumer)
        producer.dispatch(ModelTrained(model, [{'name': 'loss', 'value': 0.1}, {'name': 'accuracy', 'value': 0.9}]))     
        ```
    """
    def __init__(self):
        self.consumers = list[Consumer]()

    def register(self, *consumers: Consumer):
        """
        Registers a sequence of consumers to the producer. The producer will dispatch events to all registered
        consumers.
        """
        for consumer in consumers:
            self.consumers.append(consumer)

    def dispatch(self, message: Any):
        """
        Dispatches an event to all registered consumers. The event will be consumed by the consumers that have
        registered handlers for the event type.

        Args:
            message (Any): The event to dispatch.
        """
        for consumer in self.consumers:
            consumer.consume(message)