Public API
==========

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


Core
~~~~

.. autoclass:: frametree.core.store.Store
    :members: save, load, remove, define_frameset, create_dataset, import_dataset

.. autoclass:: frametree.core.frameset.FrameSet
    :members: add_source, add_sink, apply, save, load, row, rows, __getitem__, install_license, derive

.. autoclass:: frametree.core.axes.Axes
    :members: leaf, bases, span, is_basis, union, default, is_parent

.. autoclass:: frametree.core.column.DataSource
    :members: __getitem__, cell, cells, ids

.. autoclass:: frametree.core.column.DataSink
    :members: __getitem__, cell, cells, ids, derive

.. autoclass:: frametree.core.row.DataRow
    :members: __getitem__, __setitem__, cell, entry, entries, id, label, keys, values
