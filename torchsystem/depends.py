# Copyright Eric Cardozo.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License. 
#
# 
# For inquiries, visit the documentation at mr-mapache.github.io/torch-system/

### TODO: More work needed to be done on this file.
### While this is workings, this should be refactored with better code before it grows too much.

from typing import Generator
from inspect import signature
from contextlib import ExitStack, contextmanager
from collections.abc import Callable

class Provider:
    def __init__(self):
        self.dependency_overrides = dict()
    
    def override(self, dependency: Callable, override: Callable):
        self.dependency_overrides[dependency] = override

class Dependency:
    def __init__(self, callable: Callable):
        self.callable = callable

def resolve(function: Callable, provider: Provider, *args, **kwargs):
    parameters = signature(function).parameters
    bounded = signature(function).bind_partial(*args, **kwargs)
    exit_stack = ExitStack()
    
    for name, parameter in parameters.items():
        if name not in bounded.arguments and isinstance(parameter.default, Dependency):
            dependency = parameter.default.callable
            if dependency in provider.dependency_overrides:
                dependency = provider.dependency_overrides[dependency]
            
            dep_instance = dependency()
            
            if isinstance(dep_instance, Generator):
                bounded.arguments[name] = exit_stack.enter_context(_managed_dependency(dep_instance))
            else:
                bounded.arguments[name] = dep_instance
    
    return bounded, exit_stack

@contextmanager
def _managed_dependency(generator: Generator):
    try:
        value = next(generator)
        yield value
    finally:
        next(generator, None)   

def Depends(callable: Callable):
    """
    The Depends function is used to define a dependency for a function. The callable argument is
    a function that will be called to provide the dependency. The function can return a value or a generator in
    order to clean up resources after the function has been called.

    Args:
        callable (Callable): The function that will be called to provide the dependency.

    Returns: 
        Dependency: A Dependency object that can be used as a default value for a function parameter
    """
    return Dependency(callable)

def inject(provider: Provider):
    def decorator(function: Callable):
        def wrapper(*args, **kwargs):
            bounded, exit_stack = resolve(function, provider, *args, **kwargs)
            with exit_stack:
                return function(*bounded.args, **bounded.kwargs)
        return wrapper
    return decorator
