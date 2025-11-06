# Development Guidelines

## SOLID Principles

**Single Responsibility**: One class, one job. Keep UI separate from business logic. Isolate validation into its own class.

**Open/Closed**: Extend through interfaces, not by modifying existing code. For example, create a `PaymentMethod` interface, then add `CreditCard` and `PayPal` implementations.

**Liskov Substitution**: Subclasses must work anywhere the parent works. Don't throw new exceptions in overrides.

**Interface Segregation**: Small, focused interfaces. Split `Worker` into `Workable`, `Eatable`, `Sleepable`. Implement only what you need.

**Dependency Inversion**: Inject dependencies. Define abstract `DataSource`, inject concrete `ApiClient` or `LocalDatabase`.

## Core Rules

**DRY**: Extract repeated patterns into reusable widgets. Use mixins for shared behavior.

**KISS**: Use Flutter's built-in widgets. Avoid over-engineering. Start simple.

**YAGNI**: Build what you need now, not what you might need later. No premature optimization.