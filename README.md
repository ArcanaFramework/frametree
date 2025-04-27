# FrameTree

[![CI/CD](https://github.com/ArcanaFramework/frametree/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/ArcanaFramework/frametree/actions/workflows/ci-cd.yml)
![Codecov](https://codecov.io/gh/ArcanaFramework/frametree/branch/main/graph/badge.svg?token=UIS0OGPST7)
![Python versions](https://img.shields.io/pypi/pyversions/frametree.svg)
![Latest Version](https://img.shields.io/pypi/v/frametree.svg)
[![Docs](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](https://arcanaframework.github.io/frametree/)

<img src="./docs/source/_static/images/logo_small.png" alt="Logo Small" style="float: right;">

FrameTree is Python framework that is used to map categorical data organised into trees
(e.g. MRI sessions for multiple subjects and visits saved in a file-system directory)
onto virtual "data frames" for analysis. Cells in these data frames can be scalars, arrays
or a set of files and/or directories stored at each node across a level in the given tree.
Derivatives are stored, along with the parameters used to derive them, back into
the store for reference and reuse by subsequent analysis steps.
Extracted metrics can be exported to actual data frames for statistical analysis.

## Documentation

Detailed documentation on FrameTree can be found at [https://arcanaframework.github.io/frametree/](https://arcanaframework.github.io/frametree/)

## Quick Installation

FrameTree can be installed for Python 3 using *pip*

```bash
    python3 -m pip install frametree
```

## Extensions for backends

Support for specific data repository platforms software or data structures (e.g. XNAT or BIDS)
are provided by extension packages (see [frametree-xnat](https://github.com/ArcanaFramework/frametree-xnat)
and [frametree-bids](https://github.com/ArcanaFramework/frametree-bids)). They can be installed with

```bash
    python3 -m pip install frametree-xnat frametree-bids
```

See the [extension template](https://github.com/ArcanaFramework/frametree-extension-template)
to get started with support for different backends

## License

This work is licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/)

![Creative Commons License: Attribution-NonCommercial-ShareAlike 4.0 International](https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png)

### Acknowledgements

The authors acknowledge the facilities and scientific and technical assistance of the
National Imaging Facility, a National Collaborative Research Infrastructure Strategy (NCRIS) capability.
