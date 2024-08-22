FrameSets
=========

"FrameSets" consist of all, or a subset thereof, data points (e.g. imaging session)
within a dataset mapped onto a set of frames. The mapping is done via gridding a
multi-dimensional grid, where the categorical variables used to distinguish the data
points form the axes. The "hierarchy" of branches (e.g. groups > subjects > sessions)
within the data tree. Consider the following example dataset consisting of imaging sessions is
sorted by subjects, then longintudinal visits

.. code-block::

    my-dataset
    ├── subject1
    │   ├── visit1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── visit2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    ├── subject2
    │   ├── visit1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── visit2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    └── subject3
        ├── visit1
        │   ├── t1w_mprage
        │   ├── t2w_space
        │   └── bold_rest
        └── visit2
            ├── t1w_mprage
            ├── t2w_space
            └── bold_rest

The leaves of the tree contain data from specific "imaging session" data points,
as designated by the combination of one of the three subject IDs and
one of the two visit IDs. Data items at the session level of the hierarchy will be
mapped onto a data frame, where each session data point correspondds to a row.

The "rows" of a data frame correspond either to individual data points in the data grid
(e.g. imaging sessions in the :class:`Clincial` axes) or lines, planes for higher layers
in the hierarchy of the data tree (e.g. subjects or study groups). For example within the
:class:`Clinical` axes, the "row frequency" of frames are

* imaging sessions
* subjects
* study groups (e.g. 'test' or 'control')
* longitudinal visits
* control-matched pairs
* batches (separate groups at separate visits)
* matched-point (matched members (e.g. test & control) across all groups and visits)
* constant/singular

Note that these "rows" do not correspond to rows of data points in the intermediate grid
conception, rather rows in the final data frame.

While the majority of data items are stored in the leaves of the tree,
data can exist for any branch. For example, an analysis may use
genomics data, which will be constant for each subject, and therefore sits at
the subject level of the tree sit in special *SUBJECT* branches

.. code-block::

    my-dataset
    ├── subject1
    │   ├── SUBJECT
    │   │   └── geneomics.dat
    │   ├── visit1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── visit2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    ├── subject2
    │   ├── SUBJECT
    │   │   └── geneomics.dat
    │   ├── visit1
    │   │   ├── t1w_mprage
    │   │   ├── t2w_space
    │   │   └── bold_rest
    │   └── visit2
    │       ├── t1w_mprage
    │       ├── t2w_space
    │       └── bold_rest
    └── subject3
        ├── SUBJECT
        │   └── geneomics.dat
        ├── visit1
        │   ├── t1w_mprage
        │   ├── t2w_space
        │   └── bold_rest
        └── visit2
            ├── t1w_mprage
            ├── t2w_space
            └── bold_rest

In this case, the genomics data maps onto a different conceptual data frame, in which
each row corresponds to a subject instead of a session.


Framesets are referenced by addresses of the form
``<store-name>//<dataset-id>[@<frameset-name>]``,
where *<store-name>* is the nickname of the store as saved by ':ref:`frametree store add`'
(see :ref:`Stores`), and *<dataset-id>* is

* the file-system path to the data directory for file-system (and BIDS) stores
* the project ID for XNAT stores

*<frameset-name>* is an optional component, which is the empty string ("") by default
differentiates between multiple frame sets to be defined on the same dataset. This allows
different exclusion criteria and parameters to be used for different analyses on the same
dataset.

For example, a project called "MYXNATPROJECT" stored in
`XNAT Central <https://central.xnat.org>`__ using the *xnat-central* nickname
created in the :ref:`Stores` Section, would be ``xnat-central//MYXNATPROJECT``.


Subsets
-------

By default all data points within the dataset are included in the frameset. However,
often there are data points that need to be removed from a given
analysis due to missing or corrupted data. Such sections need to be removed
in a way that the data points still lie on a rectangular grid within the
data axes (see :ref:`axes`) so derivatives computed over a given axis
or axes are drawn from comparable number of data points.

The ``--exclude`` option is used to specify the data points to exclude from
a dataset.

.. TODO image of excluding points in grid

.. code-block:: console

    $ frametree define '/data/imaging/my-project@manually_qcd' \
      common/clinical subject session \
      --exclude member 03,11,27


The ``include`` argument is the inverse of exclude and can be more convenient when
you only want to select a small sample or split the dataset into sections.
``include`` can be used in conjunction with ``exclude`` but not for the same
frequencies.

.. code-block:: console

    $ frametree define '/data/imaging/my-project@manually_qcd' \
      common/clinical subject session \
      --exclude member 03,11,27 \
      --include visit 1,2

You may want multiple dataset definitions for a given project/directory,
for different analyses e.g. with different subsets of IDs depending on which
scans have passed quality control, or to define training and test datasets
for machine learning. To keep these analyses separate, you can
assign a dataset definition a name, which is used differentiate between multiple
definitions stored in the same dataset project/directory. To do this via the
CLI, append the name to the dataset's ID string separated by '::', e.g.

.. code-block:: console

    $ frametree define '/data/imaging/my-project@training' \
      common/clinical group subject \
      --include member 10:20

Alternatively, frameset objects can be defined using the Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        from frametree.xnat import Xnat

        xnat_store = Xnat.load('xnat-central')
        xnat_frameset = xnat_store.define(id='MYXNATPROJECT', exclude={'member': [3, 11, 27]})



Axes
----

In addition to data frames corresponding to row frequencies that explicitly
appear in the hierarchy of the data tree (see :ref:`Columns`),
there are a number of frames that are implied and may be needed to store
derivatives of a particular analysis. In clinical imaging research studies/trials,
imaging sessions are classified by the subject who was scanned and, if applicable,
the longitudinal visit. The subjects themselves are often classified by which
group they belong to. Therefore, we can factor imaging session
classifications into

* **group** - study group (e.g. 'test' or 'control')
* **member** - ID relative to group
    * can be arbitrary or used to signify control-matched pairs
    * e.g. the '03' in 'TEST03' & 'CONT03' pair of control-matched subject IDs
* **visit** - longintudinal visit

In FrameTree, these primary classifiers are conceptualised as "axes" of a
"data space", in which data points (e.g. imaging sessions) are
laid out on a grid.

.. TODO: frameset image to go here

Depending on the hierarchy of the data tree, data belonging to these
axial frequencies may or may not have a corresponding branch to be stored in.
In these cases, new branches are created off the root of the tree to
hold the derivatives. For example, average trial performance data, calculated
at each visit and the age difference between matched-control pairs, would
need to be stored in new sub-branches for visits and members, respectively.

.. code-block::

    my-dataset
    ├── TIMEPOINT
    │   ├── visit1
    │   │   └── avg_trial_performance
    │   └── visit2
    │       └── avg_trial_performance
    ├── MEMBER
    │   ├── member1
    │   │   └── age_diff
    │   └── member2
    │       └── age_diff
    ├── group1
    │   ├── member1
    │   │   ├── visit1
    │   │   │   ├── t1w_mprage
    │   │   │   ├── t2w_space
    │   │   │   └── bold_rest
    │   │   └── visit2
    │   │       ├── t1w_mprage
    │   │       ├── t2w_space
    │   │       └── bold_rest
    │   └── member2
    │       ├── visit1
    │       │   ├── t1w_mprage
    │       │   ├── t2w_space
    │       │   └── bold_rest
    │       └── visit2
    │           ├── t1w_mprage
    │           ├── t2w_space
    │           └── bold_rest
    └── group2
        |── member1
        │   ├── visit1
        │   │   ├── t1w_mprage
        │   │   ├── t2w_space
        │   │   └── bold_rest
        │   └── visit2
        │       ├── t1w_mprage
        │       ├── t2w_space
        │       └── bold_rest
        └── member2
            ├── visit1
            │   ├── t1w_mprage
            │   ├── t2w_space
            │   └── bold_rest
            └── visit2
                ├── t1w_mprage
                ├── t2w_space
                └── bold_rest

In this framework, ``subject`` IDs are equivalent to the combination of
``group + member`` IDs and ``session`` IDs are equivalent to the combination of
``group + member + visit`` IDs. There are,  2\ :sup:`N` combinations of
the axial frequencies for a given data tree, where ``N`` is the depth of the tree
(i.e. ``N=3`` in this case).

.. TODO: 3D plot of frameset

Note that the frameset of a particular dataset can have a single point along any
given dimension (e.g. one study group or visit) and still exist in the data
space. Therefore, when creating data spaces it is better to be inclusive of
potential categories to make them more general.

.. TODO: another 3D frameset plot

All combinations of the data spaces axes are given a name within
:class:`.Axes` enums. In the case of the :class:`.medimage.Clinical`
data space, the members are

* **group** (group)
* **member** (member)
* **visit** (visit)
* **session** (member + group + visit),
* **subject** (member + group)
* **groupedvisit** (group + visit)
* **matchedvisit** (member + visit)
* **dataset** ()

If they are not present in the data tree, alternative row frequencies are
stored in new branches under the dataset root, in the same manner as data space
axes

.. code-block::

    my-dataset
    ├── BATCH
    │   ├── group1_visit1
    │   │   └── avg_connectivity
    │   ├── group1_visit2
    │   │   └── avg_connectivity
    │   ├── group2_visit1
    │   │   └── avg_connectivity
    │   └── group2_visit2
    │       └── avg_connectivity
    ├── MATCHEDPOINT
    │   ├── member1_visit1
    │   │   └── comparative_trial_performance
    │   ├── member1_visit2
    │   │   └── comparative_trial_performance
    │   ├── member2_visit1
    │   │   └── comparative_trial_performance
    │   └── member2_visit2
    │       └── comparative_trial_performance
    ├── group1
    │   ├── member1
    │   │   ├── visit1
    │   │   │   ├── t1w_mprage
    │   │   │   ├── t2w_space
    │   │   │   └── bold_rest
    │   │   └── visit2
    │   │       ├── t1w_mprage
    │   │       ├── t2w_space
    │   │       └── bold_rest
    │   └── member2
    │       ├── visit1
    │       │   ├── t1w_mprage
    │       │   ├── t2w_space
    │       │   └── bold_rest
    │       └── visit2
    │           ├── t1w_mprage
    │           ├── t2w_space
    │           └── bold_rest
    └── group2
        |── member1
        │   ├── visit1
        │   │   ├── t1w_mprage
        │   │   ├── t2w_space
        │   │   └── bold_rest
        │   └── visit2
        │       ├── t1w_mprage
        │       ├── t2w_space
        │       └── bold_rest
        └── member2
            ├── visit1
            │   ├── t1w_mprage
            │   ├── t2w_space
            │   └── bold_rest
            └── visit2
                ├── t1w_mprage
                ├── t2w_space
                └── bold_rest

.. TODO Should include example of weird data hierarchy using these frequencies
.. and how the layers add to one another

For stores that support datasets with arbitrary tree structures
(i.e. :class:`.FileSystem`), the "data axes" and the hierarchy of layers
in the data tree needs to be provided. Data axes are explained in more
detail in :ref:`axes`. However, for the majority of datasets in the
medical imaging field, the :class:`frametree.medimage.data.Clinical` is
appropriate.


.. code-block:: console

    $ frametree define '/data/imaging/my-project' common/clinical group session


Alternatively via the Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        from frametree.common import Clinical, FileSystem

        fs_frameset = FileSystem().define(
            id='/data/imaging/my-project',
            # Define the hierarchy of the dataset in which imaging session
            # sub-directories are separated into directories via their study group
            # (i.e. test & control)
            axes=Clinical,
            hierarchy=['group', 'session'])

For datasets where the fundamental hierarchy of the storage system is fixed
(e.g. XNAT), you may need to infer the data point IDs along an axis
by decomposing a branch label following a given naming convention.
This is specified via the ``id-inference`` argument to the dataset definition.
For example, given a an XNAT project with the following structure and a naming
convention where the subject ID is composed of the group and member ID,
*<GROUPID><MEMBERID>*, and the session ID is composed of the subject ID and visit,
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

IDs for group, member and visit can be inferred from the subject and session
IDs, by providing the frequency of the ID to decompose and a
regular-expression (in Python syntax) to decompose it with. The regular
expression should contain named groups that correspond to row frequencies of
the IDs to be inferred, e.g.

.. code-block:: console

    $ frametree define 'xnat-central//MYXNATPROJECT' \
      --id-inference subject '(?P<group>[A-Z]+)_(?P<member>\d+)' \
      --id-inference session '[A-Z0-9]+_MR(?P<visit>\d+)'


.. _FrameTree: https://frametree.readthedocs.io
.. _XNAT: https://xnat.org
.. _BIDS: https://bids.neuroimaging.io
