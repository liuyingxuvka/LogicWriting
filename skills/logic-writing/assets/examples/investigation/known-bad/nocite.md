# Free-threaded Python: supported, not the default

Short answer: as of Python 3.14, the free-threaded build (CPython without the global interpreter lock) is officially supported and no longer experimental, but it is still an optional build. The standard build keeps the lock, and nothing in the release notes says that will change in a given release [What's New 3.14].

## From experimental to supported

The change is recent. In Python 3.13 the free-threaded mode shipped as an experimental feature and was not enabled by default [What's New 3.13]. Python 3.14 finished the implementation described in PEP 703 and declared the start of what the core team calls phase II: the build is supported and will not be removed without a deprecation period, but users have to choose it [What's New 3.14].

## What it costs

Support does not mean it is free. The 3.14 release notes put the slowdown for single-threaded code at roughly 5-10%, depending on the platform and C compiler [What's New 3.14]. That range is the project's own estimate, not a benchmark of your service, so the only number that matters for a migration decision is the one you measure on your own workload.

## Will it become the default?

Not on any announced schedule. Making the free-threaded build the default, or the only build, is what the plan calls phase III, and the 3.14 release notes say that decision is still open and depends on factors inside CPython and in the wider community [What's New 3.14]. PEP 779, which set the bar for reaching the supported stage, says plainly that its criteria cover only that step and that the default decision is a different question. Anyone telling you the switch is coming in the next release is going beyond what the project has said.

## What to do

It is reasonable to start testing your service on the free-threaded build now, because the project has committed to keeping it. It is not reasonable to plan a migration around it becoming the default by a particular date. One caution: these sources describe CPython's own position, not whether the libraries your service depends on work without the lock, so check those before any trial goes beyond a test environment. Revisit the plan when a phase III decision is announced.
