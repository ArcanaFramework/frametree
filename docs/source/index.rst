.. _home:

FrameTree
=========

FrameTree is a Python package that sets out to bridge the gap between
the semi-structured data trees that file-based data are typically stored in,
and the tabular data frames used in statistical analysis. This
transformation is abstract, with the source data remaining within original data
tree and generated derivatives stored alongside them.

Data store interactions are mediated by well-defined interfaces, making it possible to write
backends for different storage systems and data structures. In addition to the generic
"file system" backend, backends for XNAT_ and BIDS_ are currently supported, with a prototype started
for Flywheel_. FrameTree facilitates pulling data from the data store to a (typically
neighbouring) computing resource, and then uploading the processed data alongside the
original data in a location that can be accessed by subsequent analysis steps. In this
manner chains of modular pipelines can be applied and used to produce output metrics
that can be fed directly into statistical analysis.

The key elements of FrameTree's data model are:

* :ref:`Stores` - encapsulations of tree-based file storage systems
* :ref:`FrameSets` - mapping of datasets (or subsets thereof) onto a set of data frames
* :ref:`Columns` - cross-section of equivalent data types across a dataset (e.g. all T1-weighted scans across all imaging sessions)
* :ref:`Pipelines` - applied workflows and tasks on the data


.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   basic_usage
   stores
   framesets
   columns
   pipelines
   contributing

.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   CLI <cli.rst>
   API <api.rst>


Licence
-------

FrameTree is licenced under the `Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License <https://creativecommons.org/licenses/by-nc-sa/4.0/>`_
(see `LICENCE <https://raw.githubusercontent.com/Australian-Imaging-Service/frametree/master/LICENSE>`_).
Non-commercial usage is permitted freely on the condition that FrameTree is
appropriately acknowledged in related publications.


.. _Pydra: http://pydra.readthedocs.io
.. _XNAT: http://xnat.org
.. _BIDS: http://bids.neuroimaging.io/
.. _Flywheel: http://flywheel.io/
