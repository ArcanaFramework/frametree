Datasets
========

In FrameTree, a *dataset* refers to a collection of comparable data within a store,
e.g. data from a single research study, or large collection such as the
Human Connectome Project. FrameTree datasets consist of both source data and the
derivatives derived from them. Datasets are organised into trees that classify a
series of data points (e.g. imaging sessions) by a "hierarchy" of branches
(e.g. groups > subjects > sessions). For example, the following dataset consisting
of imaging sessions is sorted by subjects, then longintudinal timepoints

.. code-block::

    my-dataset
    ├── subject1
    │   ├── timepoint1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── timepoint2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    ├── subject2
    │   ├── timepoint1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── timepoint2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    └── subject3
        ├── timepoint1
        │   ├── t1w_mprage
        │   ├── t2w_space
        │   └── bold_rest
        └── timepoint2
            ├── t1w_mprage
            ├── t2w_space
            └── bold_rest

The leaves of the tree contain data from specific "imaging session" data points,
as designated by the combination of one of the three subject IDs and
one of the two timepoint IDs.

While the majority of data items are stored in the leaves of the tree,
data can exist for any branch. For example, an analysis may use
genomics data, which will be constant for each subject, and therefore sits at
the subject level of the tree sit in special *SUBJECT* branches

.. code-block::

    my-dataset
    ├── subject1
    │   ├── SUBJECT
    │   │   └── geneomics.dat
    │   ├── timepoint1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── timepoint2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    ├── subject2
    │   ├── SUBJECT
    │   │   └── geneomics.dat
    │   ├── timepoint1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── timepoint2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    └── subject3
        ├── SUBJECT
        │   └── geneomics.dat
        ├── timepoint1
        │   ├── t1w_mprage
        │   ├── t2w_space
        │   └── bold_rest
        └── timepoint2
            ├── t1w_mprage
            ├── t2w_space
            └── bold_rest


In the CLI, datasets are referred to by ``<store-nickname>//<dataset-id>[@<dataset-name>]``,
where *<store-name>* is the nickname of the store as saved by ':ref:`frametree store add`'
(see :ref:`Stores`), and *<dataset-id>* is

* the file-system path to the data directory for file-system (and BIDS) stores
* the project ID for XNAT stores

*<dataset-id>* is an optional component ("default" by default), which specifies a
unique namespace for the dataset, and derivatives created within it. This enables
multiple FrameTree datasets to be defined on the same data, with different exclusion
criteria and analyses applied to them.

For example, a project called "MYXNATPROJECT" stored in
`XNAT Central <https://central.xnat.org>`__ using the *xnat-central* nickname
created in the :ref:`Stores` Section, would be ``xnat-central//MYXNATPROJECT``.

Alternatively, dataset objects can be created directly via the Python API using
the :meth:`.Store.dataset` method. For example, to define a new dataset
corresponding to *MYXNATPROJECT*

.. code-block:: python

    xnat_dataset = xnat_store.dataset(id='MYXNATPROJECT')


Subsets
-------

Often there are data points that need to be removed from a given
analysis due to missing or corrupted data. Such sections need to be removed
in a way that the data points still lie on a rectangular grid within the
data space (see :ref:`data_spaces`) so derivatives computed over a given axis
or axes are drawn from comparable number of data points.

.. note::
    Somewhat confusingly the "data points" referred to in this section
    actually correspond to "data rows" in the frames used in analyses.
    However, you can think of a 2 or 3 (or higher) dimensional grid as
    being flattened out into a 1D array to form a data frame in the
    same way as numpy's ``ravel()`` method does to higher dimensional
    arrays. The different types of data collected at each data point
    (e.g. imaging session) can then be visuallised as expanding out to
    form the row of the data frame.

The ``--exclude`` option is used to specify the data points to exclude from
a dataset.

.. TODO image of excluding points in grid

.. code-block:: console

    $ frametree dataset define '/data/imaging/my-project@manually_qcd' \
      common:Clinical subject session \
      --exclude member 03,11,27


The ``include`` argument is the inverse of exclude and can be more convenient when
you only want to select a small sample or split the dataset into sections.
``include`` can be used in conjunction with ``exclude`` but not for the same
frequencies.

.. code-block:: console

    $ frametree dataset define '/data/imaging/my-project@manually_qcd' \
      common:Clinical subject session \
      --exclude member 03,11,27 \
      --include timepoint 1,2

You may want multiple dataset definitions for a given project/directory,
for different analyses e.g. with different subsets of IDs depending on which
scans have passed quality control, or to define training and test datasets
for machine learning. To keep these analyses separate, you can
assign a dataset definition a name, which is used differentiate between multiple
definitions stored in the same dataset project/directory. To do this via the
CLI, append the name to the dataset's ID string separated by '::', e.g.

.. code-block:: console

    $ frametree dataset define '/data/imaging/my-project@training' \
      common:Clinical group subject \
      --include member 10:20



.. _data_spaces:

Spaces
------

In addition to data frames corresponding to row frequencies that explicitly
appear in the hierarchy of the data tree (see :ref:`data_columns`),
there are a number of frames that are implied and may be needed to store
derivatives of a particular analysis. In clinical imaging research studies/trials,
imaging sessions are classified by the subject who was scanned and, if applicable,
the longitudinal timepoint. The subjects themselves are often classified by which
group they belong to. Therefore, we can factor imaging session
classifications into

* **group** - study group (e.g. 'test' or 'control')
* **member** - ID relative to group
    * can be arbitrary or used to signify control-matched pairs
    * e.g. the '03' in 'TEST03' & 'CONT03' pair of control-matched subject IDs
* **timepoint** - longintudinal timepoint

In FrameTree, these primary classifiers are conceptualised as "axes" of a
"data space", in which data points (e.g. imaging sessions) are
laid out on a grid.

.. TODO: grid image to go here

Depending on the hierarchy of the data tree, data belonging to these
axial frequencies may or may not have a corresponding branch to be stored in.
In these cases, new branches are created off the root of the tree to
hold the derivatives. For example, average trial performance data, calculated
at each timepoint and the age difference between matched-control pairs, would
need to be stored in new sub-branches for timepoints and members, respectively.

.. code-block::

    my-dataset
    ├── TIMEPOINT
    │   ├── timepoint1
    │   │   └── avg_trial_performance
    │   └── timepoint2
    │       └── avg_trial_performance
    ├── MEMBER
    │   ├── member1
    │   │   └── age_diff
    │   └── member2
    │       └── age_diff
    ├── group1
    │   ├── member1
    │   │   ├── timepoint1
    │   │   │   ├── t1w_mprage
    │   │   │   ├── t2w_space
    │   │   │   └── bold_rest
    │   │   └── timepoint2
    │   │       ├── t1w_mprage
    │   │       ├── t2w_space
    │   │       └── bold_rest
    │   └── member2
    │       ├── timepoint1
    │       │   ├── t1w_mprage
    │       │   ├── t2w_space
    │       │   └── bold_rest
    │       └── timepoint2
    │           ├── t1w_mprage
    │           ├── t2w_space
    │           └── bold_rest
    └── group2
        |── member1
        │   ├── timepoint1
        │   │   ├── t1w_mprage
        │   │   ├── t2w_space
        │   │   └── bold_rest
        │   └── timepoint2
        │       ├── t1w_mprage
        │       ├── t2w_space
        │       └── bold_rest
        └── member2
            ├── timepoint1
            │   ├── t1w_mprage
            │   ├── t2w_space
            │   └── bold_rest
            └── timepoint2
                ├── t1w_mprage
                ├── t2w_space
                └── bold_rest

In this framework, ``subject`` IDs are equivalent to the combination of
``group + member`` IDs and ``session`` IDs are equivalent to the combination of
``group + member + timepoint`` IDs. There are,  2\ :sup:`N` combinations of
the axial frequencies for a given data tree, where ``N`` is the depth of the tree
(i.e. ``N=3`` in this case).

.. TODO: 3D plot of grid

Note that the grid of a particular dataset can have a single point along any
given dimension (e.g. one study group or timepoint) and still exist in the data
space. Therefore, when creating data spaces it is better to be inclusive of
potential categories to make them more general.

.. TODO: another 3D grid plot

All combinations of the data spaces axes are given a name within
:class:`.Axes` enums. In the case of the :class:`.medimage.Clinical`
data space, the members are

* **group** (group)
* **member** (member)
* **timepoint** (timepoint)
* **session** (member + group + timepoint),
* **subject** (member + group)
* **batch** (group + timepoint)
* **matchedpoint** (member + timepoint)
* **dataset** ()

If they are not present in the data tree, alternative row frequencies are
stored in new branches under the dataset root, in the same manner as data space
axes

.. code-block::

    my-dataset
    ├── BATCH
    │   ├── group1_timepoint1
    │   │   └── avg_connectivity
    │   ├── group1_timepoint2
    │   │   └── avg_connectivity
    │   ├── group2_timepoint1
    │   │   └── avg_connectivity
    │   └── group2_timepoint2
    │       └── avg_connectivity
    ├── MATCHEDPOINT
    │   ├── member1_timepoint1
    │   │   └── comparative_trial_performance
    │   ├── member1_timepoint2
    │   │   └── comparative_trial_performance
    │   ├── member2_timepoint1
    │   │   └── comparative_trial_performance
    │   └── member2_timepoint2
    │       └── comparative_trial_performance
    ├── group1
    │   ├── member1
    │   │   ├── timepoint1
    │   │   │   ├── t1w_mprage
    │   │   │   ├── t2w_space
    │   │   │   └── bold_rest
    │   │   └── timepoint2
    │   │       ├── t1w_mprage
    │   │       ├── t2w_space
    │   │       └── bold_rest
    │   └── member2
    │       ├── timepoint1
    │       │   ├── t1w_mprage
    │       │   ├── t2w_space
    │       │   └── bold_rest
    │       └── timepoint2
    │           ├── t1w_mprage
    │           ├── t2w_space
    │           └── bold_rest
    └── group2
        |── member1
        │   ├── timepoint1
        │   │   ├── t1w_mprage
        │   │   ├── t2w_space
        │   │   └── bold_rest
        │   └── timepoint2
        │       ├── t1w_mprage
        │       ├── t2w_space
        │       └── bold_rest
        └── member2
            ├── timepoint1
            │   ├── t1w_mprage
            │   ├── t2w_space
            │   └── bold_rest
            └── timepoint2
                ├── t1w_mprage
                ├── t2w_space
                └── bold_rest

.. TODO Should include example of weird data hierarchy using these frequencies
.. and how the layers add to one another

For stores that support datasets with arbitrary tree structures
(i.e. :class:`.FileSystem`), the "data space" and the hierarchy of layers
in the data tree needs to be provided. Data spaces are explained in more
detail in :ref:`data_spaces`. However, for the majority of datasets in the
medical imaging field, the :class:`frametree.medimage.data.Clinical` space is
appropriate.

.. code-block:: python

    from frametree.file_system import FileSystem
    from frametree.common import Clinical

    fs_dataset = FileSystem().dataset(
        id='/data/imaging/my-project',
        # Define the hierarchy of the dataset in which imaging session
        # sub-directories are separated into directories via their study group
        # (i.e. test & control)
        space=Clinical,
        hierarchy=['group', 'session'])

For datasets where the fundamental hierarchy of the storage system is fixed
(e.g. XNAT), you may need to infer the data point IDs along an axis
by decomposing a branch label following a given naming convention.
This is specified via the ``id-inference`` argument to the dataset definition.
For example, given a an XNAT project with the following structure and a naming
convention where the subject ID is composed of the group and member ID,
*<GROUPID><MEMBERID>*, and the session ID is composed of the subject ID and timepoint,
*<SUBJECTID>_MR<TIMEPOINTID>*

.. code-block::

    MY_XNAT_PROJECT
    ├── TEST01
    │   └── TEST01_MR01
    │       ├── t1w_mprage
    │       └── t2w_space
    ├── TEST02
    │   └── TEST02_MR01
    │       ├── t1w_mprage
    │       └── t2w_space
    ├── CONT01
    │   └── CONT01_MR01
    │       ├── t1w_mprage
    │       └── t2w_space
    └── CONT02
        └── CONT02_MR01
            ├── t1w_mprage
            └── t2w_space

IDs for group, member and timepoint can be inferred from the subject and session
IDs, by providing the frequency of the ID to decompose and a
regular-expression (in Python syntax) to decompose it with. The regular
expression should contain named groups that correspond to row frequencies of
the IDs to be inferred, e.g.

.. code-block:: console

    $ frametree dataset define 'xnat-central//MYXNATPROJECT' \
      --id-inference subject '(?P<group>[A-Z]+)_(?P<member>\d+)' \
      --id-inference session '[A-Z0-9]+_MR(?P<timepoint>\d+)'


.. _FrameTree: https://frametree.readthedocs.io
.. _XNAT: https://xnat.org
.. _BIDS: https://bids.neuroimaging.io
