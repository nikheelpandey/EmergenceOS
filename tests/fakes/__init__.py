"""
Fake implementations used throughout the EmergenceOS test suite.

Why fakes instead of mocks?

Fakes provide deterministic implementations of real kernel components.

Advantages
----------
* More realistic behavior
* Less brittle tests
* Easier refactoring
* Better documentation of expected behavior

These classes intentionally implement the same public contracts as their
production counterparts while remaining lightweight and deterministic.
"""