Data model
==========

FrameTree's data model sets out to bridge the gap between
the semi-structured data trees that file-based data are typically stored in,
and the tabular data frames used in statistical analysis. Note that this
transformation is abstract, with the source data remaining within original data
tree and generated derivatives stored alongside them.

The key elements of FrameTree's data model are:

* :ref:`Stores` - encapsulations of tree-based file storage systems
* :ref:`Datasets` - sets of comparable data to be jointly analysed
* :ref:`Items` - references to data elements (files, scalars, and arrays)
* :ref:`data_columns` - abstract tables within datasets
* :ref:`data_spaces` - conceptual link between tree and tabular data structures
* :ref:`data_grids` - selection of data points to be included in an analysis
