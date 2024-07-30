# FrameTree

![Tests](https://github.com/ArcanaFramework/frametree/actions/workflows/tests.yml/badge.svg)
![Codecov](https://codecov.io/gh/ArcanaFramework/frametree/branch/main/graph/badge.svg?token=UIS0OGPST7)
![Python versions](https://img.shields.io/pypi/pyversions/frametree.svg)
![Latest Version](https://img.shields.io/pypi/v/frametree.svg)
![Docs](https://github.com/ArcanaFramework/frametree/actions/workflows/docs.yml/badge.svg)

FrameTree_ is Python framework that is used to map categorical data organised into trees
(e.g. subject data organised in file-system directory) onto virtual "data frames". Cell in
these data frames can be scalars, arrays or a set of files and/or directories stored at
each node across a level in the given tree. Metrics extracted from the data in these frames
are stored alongside the original data, and are able to be fed into statistical analysis.

FrameTree_ manages all interactions with data stores. Support for specific 
specific repository software or data structures (e.g. XNAT or BIDS).
Intermediate outputs are stored, along with the parameters used to derive them, back into
the store for reuse by subsequent analysis steps.

Analysis workflows are constructed and executed using the Pydra_ dataflow API, and can
either be run locally or submitted to cloud or HPC clusters using Pydra_'s various
execution plugins. For a requested output, FrameTree determines the required processing
steps by querying the store to check for missing intermediate outputs and parameter
changes before constructing the required workflow graph.

## Documentation

Detailed documentation on FrameTree can be found at [https://frametree.readthedocs.io](https://frametree.readthedocs.io)


## Quick Installation

FrameTree-core can be installed for Python 3 using *pip*::

   $ python3 -m pip install frametree


## License

This work is licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/)

![Creative Commons License: Attribution-NonCommercial-ShareAlike 4.0 International](https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png)


### Acknowledgements

The authors acknowledge the facilities and scientific and technical assistance of the National Imaging Facility, a National Collaborative Research Infrastructure Strategy (NCRIS) capability.

[FrameTree]: http://frametree.readthedocs.io
[Pydra]: http://pydra.readthedocs.io
[XNAT]: http://xnat.org
[BIDS]: http://bids.neuroimaging.io/
[Environment Modules]: http://modules.sourceforge.net
