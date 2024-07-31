Application Programming Interface
=================================

The core of Arcana's framework is located under the ``frametree.core`` sub-package,
which contains all the domain-independent logic. Domain-specific extensions
for alternative data stores, dimensions and formats should be placed in
``frametree.data.stores``, ``frametree.data.spaces`` and ``frametree.data.types``
respectively.


.. warning::
    Under construction



Data Model
----------

Core
~~~~

.. autoclass:: frametree.core.data.store.DataStore

.. autoclass:: frametree.core.data.set.Dataset
    :members: add_source, add_sink

.. autoclass:: frametree.core.data.space.DataSpace

.. autoclass:: frametree.core.data.row.DataRow

.. autoclass:: frametree.core.data.column.DataSource

.. autoclass:: frametree.core.data.column.DataSink

.. autoclass:: frametree.core.data.datatype.DataType
    :members: get, put

.. autoclass:: frametree.core.data.datatype.FileSet

.. autoclass:: frametree.core.data.datatype.Field

.. autoclass:: frametree.core.data.datatype.BaseFile

.. autoclass:: frametree.core.data.datatype.Directory

.. autoclass:: frametree.core.data.datatype.WithSideCars


Stores
~~~~~~

.. autoclass:: frametree.dirtree.data.SimpleStore

.. autoclass:: frametree.bids.data.Bids

.. autoclass:: frametree.medimage.data.Xnat

.. autoclass:: frametree.medimage.data.XnatViaCS
    :members: generate_xnat_command, generate_dockerfile, create_wrapper_image


Processing
----------

.. autoclass:: frametree.core.analysis.pipeline.Pipeline


Enums
~~~~~

.. autoclass:: frametree.core.enum.ColumnSalience
    :members:
    :undoc-members:
    :member-order: bysource

.. autoclass:: frametree.core.enum.ParameterSalience
    :members:
    :undoc-members:
    :member-order: bysource

.. autoclass:: frametree.core.enum.DataQuality
    :members:
    :undoc-members:
    :member-order: bysource
