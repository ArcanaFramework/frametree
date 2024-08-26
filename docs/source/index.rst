.. _home:

FrameTree
=========

FrameTree is a Python package that sets out to bridge the gap between
the tree-like structures that file-based data are typically stored in, and the tabular
data frames used in statistical analysis. This transformation is abstract, with the
source data remaining within original data tree and generated derivatives stored
alongside them.

Data store interactions are mediated by clearly defined interfaces, making it possible to write
backends for different storage systems and data structures. In addition to the generic
"file system" backend, backends for XNAT_ and BIDS_ are currently supported, with a prototype started
for Flywheel_. FrameTree facilitates pulling data from the data store to a (typically
neighbouring) computing resource, and then uploading the processed data alongside the
original data in a location that can be accessed by subsequent analysis steps. In this
manner chains of modular pipelines can be applied and used to produce output metrics
that can be fed directly into statistical analysis.

The key elements of FrameTree's data model are:

* :ref:`Stores` - tree-like file storage system backends (e.g. file systems, XNAT_, BIDS_, Flywheel_)
* :ref:`FrameSets` - virtual mapping of datasets (or subsets thereof) onto a set of data frames
* :ref:`Columns` - cross-section of data acquisitions across a frameset (e.g. anatomical MRI, subject's age)
* :ref:`Pipelines` - workflows and tasks applied to a frameset


Installation
------------

FrameTree requires a recent version of Python (>=3.8) to run. So you may
need to upgrade your Python version before it is installed. It can be installed along
with its dependencies from the `Python Package Index <http://pypi.org>`_ using *Pip3*

.. code-block:: console

    $ pip3 install frametree

To add support for XNAT_ or BIDS_ stores you will also need to install the respective
extension modules ``frametree-xnat`` and ``frametree-bids``, e.g.


.. code-block:: console

    $ pip3 install frametree-xnat frametree-bids


Licence
-------

FrameTree is licenced under the `Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License <https://creativecommons.org/licenses/by-nc-sa/4.0/>`_
(see `LICENCE <https://raw.githubusercontent.com/Australian-Imaging-Service/frametree/master/LICENSE>`_).
Non-commercial usage is permitted freely on the condition that FrameTree is
appropriately acknowledged in related publications.


.. toctree::
   :maxdepth: 2
   :hidden:

   basic_usage
   stores
   frame_sets
   columns
   pipelines
   developer

.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   CLI <cli.rst>
   API <api.rst>



.. _Pydra: http://pydra.readthedocs.io
.. _XNAT: http://xnat.org
.. _BIDS: http://bids.neuroimaging.io/
.. _Flywheel: http://flywheel.io/
