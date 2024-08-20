.. _home:

FrameTree
=========

FrameTree is a Python package used to analyse file-based datasets stored in tree-like
structures "in-place". It does this by virtually mapping the tree structures onto
"data frames" with rows and columns, so that metrics derived from them can be fed
directly into statistical packages such as Pandas and R. This facilitates, pulling data
from the data store to a (typically neighbouring) computing resource, and then uploading
the processed data alongside the original data.

Data store interactions are abstracted by modular handlers, making it possible to write
backens for different storage systems. Currently, XNAT_ and BIDS_ backends are supported,
with a prototype started for Flywheel_.

FrameTree's data model sets out to bridge the gap between
the semi-structured data trees that file-based data are typically stored in,
and the tabular data frames used in statistical analysis. Note that this
transformation is abstract, with the source data remaining within original data
tree and generated derivatives stored alongside them.

The key elements of FrameTree's data model are:

* :ref:`Stores` - encapsulations of tree-based file storage systems
* :ref:`Datasets` - sets of comparable data to be jointly analysed
* :ref:`data_columns` - abstract tables within datasets



.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   basic_usage
   stores
   datasets
   columns

.. toctree::
   :maxdepth: 2
   :caption: Development
   :hidden:

   contributing
   new_domains
   alternative_backends

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
