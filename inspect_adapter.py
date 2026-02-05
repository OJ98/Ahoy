#!/usr/bin/env python3
"""Script to inspect the BSPL Adapter class"""
import inspect
from bspl.adapter import Adapter

# Get the constructor
sig = inspect.signature(Adapter.__init__)
print('ADAPTER CONSTRUCTOR SIGNATURE:')
print(f'def __init__{sig}')
print()

print('PARAMETER DETAILS:')
for param_name, param in sig.parameters.items():
    if param_name != 'self':
        annotation = param.annotation if param.annotation != inspect.Parameter.empty else "no annotation"
        default = param.default if param.default != inspect.Parameter.empty else "REQUIRED"
        print(f'  {param_name}: {annotation}, default={default}')

print()
print('DOCSTRING:')
print(Adapter.__init__.__doc__)

print()
print('=== CHECKING FOR MULTI-ROLE METHODS ===')
# Look for methods that might handle multiple roles
methods = inspect.getmembers(Adapter, predicate=inspect.ismethod)
functions = inspect.getmembers(Adapter, predicate=inspect.isfunction)

print('\nAll public methods:')
for name, _ in functions:
    if not name.startswith('_'):
        print(f'  - {name}()')

print()
print('=== CHECKING roles ATTRIBUTE ===')
# Get the constructor source to see how roles are handled
source_lines = inspect.getsourcelines(Adapter.__init__)[0]
for i, line in enumerate(source_lines):
    if 'self.roles' in line:
        # Print context
        start = max(0, i-2)
        end = min(len(source_lines), i+3)
        print(f'\nLine {i}: Context around "self.roles"')
        for j in range(start, end):
            print(f'  {j}: {source_lines[j]}', end='')
