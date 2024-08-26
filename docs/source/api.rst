Application Programming Interface
=================================

Core
~~~~

.. autoclass:: frametree.core.store.Store

.. autoclass:: frametree.core.frameset.FrameSet
    :members: add_source, add_sink, apply, save, load, row, rows, __getitem__, install_license, derive

.. autoclass:: frametree.core.axes.Axes

.. autoclass:: frametree.core.row.DataRow

.. autoclass:: frametree.core.column.DataSource

.. autoclass:: frametree.core.column.DataSink


Available Backends
~~~~~~~~~~~~~~~~~~

.. autoclass:: frametree.common.FileSystem

.. autoclass:: frametree.bids.Bids

.. autoclass:: frametree.xnat.Xnat

.. autoclass:: frametree.xnat.XnatViaCS


Available Axes
~~~~~~~~~~~~~~

.. autoclass:: frametree.common.Samples

.. autoclass:: frametree.common.Clinical



Markers
~~~~~~~

.. autoclass:: frametree.core.salience.ColumnSalience
    :members:
    :undoc-members:
    :member-order: bysource

.. autoclass:: frametree.core.salience.ParameterSalience
    :members:
    :undoc-members:
    :member-order: bysource

.. autoclass:: frametree.core.salience.CheckSalience
    :members:
    :undoc-members:
    :member-order: bysource

.. autoclass:: frametree.core.salience.CheckStatus
    :members:
    :undoc-members:
    :member-order: bysource

.. autoclass:: frametree.core.quality.DataQuality
    :members:
    :undoc-members:
    :member-order: bysource
