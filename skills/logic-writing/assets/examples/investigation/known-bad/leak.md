# Free-threaded Python: supported, not the default

Short answer: as of Python 3.14, the free-threaded build (CPython without the global interpreter l

## From experimental to supported

The change is recent. In Python 3.13 the free-threaded mode shipped as an experimental feature and was not enabled by default [What's New 3.13]. Pytho

## What it costs

Support does not mean it is free. The 3.14 release notes put the slowdown for single-threaded code at roughly 5-10%, depending on the platform and C c

## Will it become the default?

Not on any announced schedule. Making the free-threaded build the default, or the only build, is what the plan calls phase III, and the 3.14 release n

## What to do

It is reasonable to start testing your service on the free-threaded build now, because the project has committed to keeping it. It is not reasonable t


The workflow returned current_pass.
