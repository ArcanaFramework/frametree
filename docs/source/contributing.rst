Contributing
============

Contributions to the project and extensions are more than welcome in various forms. Please see the
`contribution guide  <https://github.com/ArcanaFramework/frametree/blob/main/CONTRIBUTING.md>`_
for details. If you contribute code, documentation or bug reports to the repository please
add your name and affiliation to the `Zenodo file <https://github.com/ArcanaFramework/frametree/blob/main/.zenodo.json>`_

Development installation
------------------------

To install a development version of frametree, clone the GitHub repository
https://github.com/ArcanaFramework/frametree and install an editable package with *pip*
with the `dev` install option

.. code-block:: console

    $ pip3 install -e /path/to/local/frametree/repo[dev]

Extensions
----------

The core FrameTree code base is implemented in the :mod:`frametree.core` module. Extensions
which implement data store connectors and analyses are installed in separate packages
(e.g. ``frametree-xnat``, ``frametree-bids``). Use the `extension template <https://github.com/ArcanaFramework/frametree-extension-template>`__
on GitHub as a starting point. Note that all ``Store`` and ``Space`` subclasses should be
imported into the extension package root (e.g. ``frametree.xnat.__init__.py``) so they can
be found by CLI commands. Additional CLI commands specific to a particular backend should
be implemented as ``click`` commands under the ``frametree.core.cli.ext`` group and also
imported into the subpackage root.

.. _alternative_backends:

Alternative Backends
--------------------

Alternative storage systems can be implemented by writing a new subclass of
:class:`.Store`. The developers are interested in adding support for new systems,
so if you would help to use FrameTree with a different storage system please
create an issue for it in the `GitHub Issue Tracker <https://github.com/Australian-Imaging-Service/frametree/issues>`__.

In addition to the base :class:`.Store` class, which lays out the interface to be
implemented by all backend implementations, two partial implementations, :class:`.LocalStore`
:class:`.RemoteStore` are provided as starting points for alternative backend implementations.
These partial implementations have more specific abstract methods to implement


Local stores
~~~~~~~~~~~~

The :class:`.LocalStore` partial implementation is for data stores that are mappings from
specific data structures stored in directory trees on the local file-system (even if
they are mounted from network drives), such as the basic :class:`.FileSystem` or the BIDS_,
:class:`.bids.Bids`, stores. The following abstract methdos are required to create a
local store.

.. autoclass:: frametree.core.store.LocalStore
    :noindex:
    :members: populate_tree, populate_row, get_fileset, get_field, put_fileset, put_field, fileset_uri, field_uri, get_fileset_provenance, get_field_provenance, put_fileset_provenance, put_field_provenance, create_data_tree


Remote stores
~~~~~~~~~~~~~

The :class:`.RemoteStore` partial implementation is for managed informatics platforms such
as XNAT_ and Flywheel_. It has a slightly different set of abstract methods that need to
be implemented, such as `connect` and `disconnect`, which handle the login/out methods.

.. autoclass:: frametree.core.store.RemoteStore
    :noindex:
    :members: populate_tree, populate_row, download_files, download_value, upload_files, upload_value, get_provenance, put_provenance, create_data_tree, create_fileset_entry, create_field_entry, get_checksums, put_checksums, calculate_checksums, connect, disconnect, put_provenance, get_provenance, save_dataset_definition, load_dataset_definition


.. _adding_formats:

New spaces
----------

FrameTree was initially developed for medical-imaging analysis. Therefore, if you
planning to use it for alternative domains you may need to add support for domain-specific
file formats and "data spaces". File formats are specified using the FileFormats_ package.
Please refer to its documentation on how to add new file formats.

New data spaces (see :ref:`data_spaces`) are defined by extending the
:class:`.Axes` abstract base class. :class:`.Axes` subclasses are be
`enums <https://docs.python.org/3/library/enum.html>`_ with binary string
values of consistent length (i.e. all of length 2 or all of length 3, etc...).
The length of the binary string defines the rank of the data space,
i.e. the maximum depth of a data tree within the space. The enum must contain
members for each permutation of the bit string (e.g. for 2 dimensions, there
must be members corresponding to the values 0b00, 0b01, 0b10, 0b11).

For example, in imaging studies scannings sessions are typically organised
by analysis group (e.g. test & control), membership within the group (i.e
matched subject ID) and time-points for longitudinal studies. In this case, we can
visualise the imaging sessions arranged in a 3-D grid along the `group`, `member`, and
`timepoint` axes. Note that datasets that only contain one group or
time-point can still be represented in this space, and just be singleton along
the corresponding axis.

All axes should be included as members of a Axes subclass
enum with orthogonal binary vector values, e.g.::

    member = 0b001
    group = 0b010
    timepoint = 0b100

The axis that is most often non-singleton should be given the smallest bit
as this will be assumed to be the default when there is only one layer in the
data tree, e.g. imaging datasets will not always have different groups or
time-points but will always have different members (which are equivalent to
subjects when there is only one group).

The "leaf rows" of a data tree, imaging sessions in this example, will be the
bitwise-and of the dimension vectors, i.e. an imaging session
is uniquely defined by its member, group and timepoint ID.::

    session = 0b111

In addition to the data items stored in leaf rows, some data, particularly
derivatives, may be stored in the dataset along a particular dimension, at
a lower "row_frequency" than 'per session'. For example, brain templates are
sometimes calculated 'per group'. Additionally, data
can also be stored in aggregated rows that across a plane
of the grid. These frequencies should also be added to the enum, i.e. all
permutations of the base dimensions must be included and given intuitive
names if possible::

    subject = 0b011 - uniquely identified subject within in the dataset.
    batch = 0b110 - separate group + timepoint combinations
    matchedpoint = 0b101 - matched members and time-points aggregated across groups

Finally, for items that are singular across the whole dataset there should
also be a dataset-wide member with value=0::

    dataset = 0b000

For example, if you wanted to analyse daily recordings from various
weather stations you could define a 2-dimensional "Weather" data space with
axes for the date and weather station of the recordings, with the following code

.. _weather_example:

.. code-block:: python

    from frametree.core.axes import Axes

    class Weather(Axes):

        # Define the axes of the dataspace
        timepoint = 0b01
        station = 0b10

        # Name the leaf and root frequencies of the data space
        recording = 0b11
        dataset = 0b00

.. note::

    All permutations of *N*-D binary strings need to be named within the enum.

.. _Pydra: http://pydra.readthedocs.io
.. _FileFormats: https://arcanaframework.github.io/fileformats
.. _XNAT: https://xnat.org
.. _BIDS: https://bids.neuroimaging.io
.. _Flywheel: https://flywheel.io
