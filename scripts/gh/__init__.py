"""GitHub PR and CI helper package.

Provides dependency-injected wrappers around ``gh``/``git`` (see
``scripts.gh.cli``) so PR/CI logic can be tested without network access.
Wiring these helpers into the Makefile's pr-*/ci-* targets is planned for
a later PR.
"""
