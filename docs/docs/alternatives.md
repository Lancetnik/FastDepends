# Some more featured DI python libraries

`FastDepend` is a very small toolkit to achieve one point: provide you with opportunity to use **FastAPI** `Depends` and typecasting everywhere.

Sometimes, more complex tools are required. In these cases I can recommend you to take a look at the following projects

## [Dishka](https://dishka.readthedocs.io/en/stable/)

Cute DI framework with scopes and agreeable API.

This library provides **IoC container** that’s genuinely useful. If you’re exhausted from endlessly passing objects just to create other objects, only to have those objects create even more — you’re not alone, and we have a solution. Not every project requires IoC container, but take a look at what we offer.

Unlike other tools, `dishka` focuses **only** on **dependency injection** without trying to solve unrelated tasks. It keeps DI in place without cluttering your code with global variables and scattered specifiers.

Key features:

* **Scopes**. Any object can have a lifespan for the entire app, a single request, or even more fractionally. Many frameworks either lack scopes completely or offer only two. Here, you can define as many scopes as needed.
* **Finalization**. Some dependencies, like database connections, need not only to be created but also carefully released. Many frameworks lack this essential feature.
* **Modular providers**. Instead of creating many separate functions or one large class, you can split factories into smaller classes for easier reuse.
* **Clean dependencies**. You don’t need to add custom markers to dependency code just to make it visible to the library.
* **Simple API**. Only a few objects are needed to start using the library.
* **Framework integrations**. Popular frameworks are supported out of the box. You can simply extend it for your needs.

Speed. The library is fast enough that performance is not a concern. In fact, it outperforms many alternatives.

## [DI](https://adriangb.com/di/)

`di` is a modern dependency injection toolkit, modeled around the simplicity of **FastAPI**'s dependency injection.

Key features:

* Intuitive: simple API, inspired by FastAPI
* Auto-wiring: `di` also supports auto-wiring using type annotations
* Scopes: inspired by `pytest scopes`, but defined by users
* Composable: decoupled internal APIs give you the flixibility to customize wiring, execution and binding.
* Performance: `di` can execute dependencies in parallel and cache results ins scopes.

## [Dependency Injector](https://python-dependency-injector.etc-labs.org)

Dependency Injector is a dependency injection framework for Python.

It helps implementing the dependency injection principle.

Key features:

* Providers
* Overriding on the fly
* Configuration (yaml, ini, json, pydantic, .env, etc)
* Resources
* Containers
* Wiring
* Asynchronous
* Typing
* Performance
* Maturity
