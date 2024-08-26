FrameSets
=========

"FrameSets" are defined on datasets consisting of a collection of experiments
classified by several categorical variables. For example, medical imaging sessions in
a clinical trial categorised by study group and subject ID, or weather readings in
a meterological analysis by date-time and weather station. These experiments are mapped
onto the rows of virtual frames for each combination of
categorical variables, with the different measurements in each experiment (e.g.
T1-weighted MRI, fMRI, atomospheric pressure, humidity), metadata (e.g.
subject year of birth, weather station altitude) or derived metrics (e.g.
average grey matter thickness, dew point) corresponding to the columns of the frames.

In the case of clinical imaging research studies/trials, imaging sessions
are classified by the subject who was scanned and, if applicable, the longitudinal
timepoint. The subjects themselves are often classified by different study groups
(e.g. test or control group). Therefore, we factor imaging session classifications into

* **group** - study group (e.g. 'test' or 'control')
* **member** - ID relative to group
    * can be arbitrary or used to signify control-matched pairs
    * e.g. the '03' in 'TEST03' & 'CONT03' pair of control-matched subject IDs
* **visit** - longintudinal timepoint

Alternatively, for a meterological analysis, data could be categorised by

* **datetime** - the time of the reading
* **location** - the location of the weather station

These "axes" are combined to produce the different "row frequencies" of the frames in
the frameset, e.g. "per-session", "per-subject", "per-location", with one frame per frequency.
In this conceptualisation, different data acquisitions belong in different frames.
For example, the "per-session" frame in a clinical imaging dataset is a combination of
three axes, *group*, *member* and *visit*, and contains the data acquired from the
imaging protocol. Whereas, the social economic status and genetic data are constant per
subject so conceptually exist within the "per subject" (group + membership ID) data frame.


Defining framesets
------------------

Frameset definitions are stored within YAML_ files inside the dataset to be analysed.
This allows analyses to be performed iteratively across different computing resources.
In the FrameTree CLI, Framesets are referenced by addresses of the form

.. code-block::

    <store-name>//<dataset-id>[@<frameset-name>]

where *<store-name>* is the nickname
of the store as saved by ':ref:`frametree store add`' (see :ref:`Stores`),
and *<dataset-id>* is an identifier that specifies the dataset within the data store, e.g.

* the file-system path to the data directory for file-system (and BIDS) stores
* the project ID for XNAT stores

For example, a project called "MYXNATPROJECT" stored the *xnat-central* store can be
defined with

.. code-block:: console

    $ # Create a reference to the Central XNAT instance and save it in the user home dir
    $ frametree store add \
      xnat-central \
      --server https://central.xnat.org \
      --user $XNAT_USER \
      --password $XNAT_PASS

    $ # Create the frameset definition and save it into the 'MYXNATPROJECT' XNAT project
    $ frametree define xnat-central//MYXNATPROJECT


Alternatively via the Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        import os
        from frametree.xnat import Xnat

        # Create a store entry
        xnat_ct = Xnat(
            server="https://central.xnat.org",
            user=os.environ["XNAT_USER"],
            password=os.environ["XNAT_PASS"]
        )

        # Save the xnat_central entry to your user profile
        xnat_ct.save("xnat-central")

        # Create the frameset definition
        frameset = xnat_ct.define(id='MYXNATPROJECT')

        # Save the frameset definition in the XNAT project
        frameset.save()

*<frameset-name>* is an optional component (empty string by default), which allows
multiple frame sets to be defined on the same dataset. This allows different exclusion
criteria and pipeline parameterisations to be used for different analyses on the same
dataset (see :ref:`Subsets` and :ref:`Pipelines`).

Axes
----

The virtual mapping from data trees to frames can be visualised by mapping
the acquired data points onto multi-dimensional grid, where the categorical variables
used to distinguish the data points form the axes of the space. In this grid, the rows
of the eventual data frames correspond either to points, lines or plains, etc...
depending on their row frequency.

.. note::
    The frameset of a particular dataset can have a single point along any
    given dimension (e.g. one study group or visit) and still exist in the data
    space. Therefore, when creating data spaces it is better to be inclusive of
    potential categories to make them more general. In these cases row frequencies
    are equivalent, e.g. `member` === `subject` if there is only one study group.

.. TODO: 3D plot of frameset

This visualisation can be useful because in addition to data frames corresponding
to row frequencies that explicitly appear in the hierarchy of the data tree, derived
metrics can exist along any orientation of the grid.

.. TODO: another 3D frameset plot

These axes are defined in Frametree by :class:`.Axes` enums. For clinical research/trials
the :class:`.medimage.Clinical` axes is defined as such

**Bases**

* **group** - study group, e.g. test or control
* **member** - matched subject groups (e.g. aged matched test/control pair)
* **visit** - visit number (e.g. longitudinal timepoint)

**Combinations**

* **session** (member + group + visit) - imaging session
* **subject** (member + group) - subject
* **groupedvisit** (group + visit) - metadata/metrics for each study group at each visit
* **matchedvisit** (member + visit) - metadata/metrics for each matched subject group at each visit
* **constant** () - metadata/metrics that are constant across the analysis


See the :ref:`Developer guide` for help on designing custom :class:`Axes` for different
domains/analyses.


Branch hierarchy
----------------

When defining a frameset on a data tree, the "hierarchy" in which the categorical variables
appear in the branches of the tree (e.g. groups > subjects > sessions) needs to be specified.
Consider the following example dataset consisting of imaging sessions is sorted by subjects,
then longintudinal visits

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
mapped onto a data frame, where each session data point correspondds to a row and the
columns correspond to different acquisition methods or derived metrics (e.g. T1-weighted
MRI scan, subject's YOB, presence of genetic marker, atomospheric pressure, rainfall,
annual rainfall, altitude, etc...).

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

In this case, the genomics data is in the "per-subject" data frame, in which
each row corresponds to a subject instead of a session.

.. TODO: frameset image to go here

Depending on the hierarchy of the data tree, data belonging to the base frequencies may
or may not have a corresponding branch to be stored in.
In these cases, new branches are created off the root of the tree to
hold the derivatives. For example, average trial performance data, calculated
at each visit and the age difference between matched-control pairs, would
need to be stored in new sub-branches for visits and members, respectively.

.. code-block::

    my-dataset
    ├── VISIT
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
(i.e. :class:`.FileSystem`), the "axes" (:ref:`Axes`) and the hierarchy of layers
in the data tree needs to be provided when defining the frameset.

.. code-block:: console

    $ frametree define '/data/imaging/my-project' group session --axes common/clinical


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
(e.g. XNAT) you don't need to provide the axes or hierarchy. However, you may need to
specify how to infer the values of an axis by decomposing the label of a branch a given
a naming convention, e.g. "CONTROL01" -> group="CONTROL" and member="01".
This inference is specified via a `regular expression (Python syntax) <https://docs.python.org/3/howto/regex.html>`__
passed to the ``id-inference`` argument of the frameset definition. For example, given an
XNAT project with the following structure and a naming convention where the subject ID is composed of the
group and member ID, *<GROUPID><MEMBERID>*, and the session ID is composed of the subject
ID and visit, *<SUBJECTID>_MR<VISITID>*

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
      --id-inference group 'subject:([A-Z]+)_\d+' \
      --id-inference member 'subject:[A-Z]+_(\d+)' \
      --id-inference visit 'subject:[A-Z0-9]+_MR(\d+)'


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
      subject session \
      --axes common/clinical \
      --exclude member 03,11,27


The ``include`` argument is the inverse of exclude and can be more convenient when
you only want to select a small sample or split the dataset into sections.
``include`` can be used in conjunction with ``exclude`` but not for the same
frequencies.

.. code-block:: console

    $ frametree define '/data/imaging/my-project@manually_qcd' \
      subject session \
      --axes common/clinical \
      --exclude member 03,11,27 \
      --include visit 1,2

You can also pass a range of IDs, *<start>:<finish>* like you would in Python slicing. This
can be used to partition a dataset into separate framesets for machine learning training
and testing, e.g. to partition a dataset with 100 members/subject into subjects 1-80 for
training and subjects 80-100 for testing you would use

.. code-block:: console

    $ # Partition the dataset into training and test framesets
    $ frametree define '/data/imaging/my-project@training' \
      group subject \
      --axes common/clinical \
      --include member 1:81
    $ frametree define '/data/imaging/my-project@test' \
      group subject \
      --axes common/clinical \
      --include member 81:101

Alternatively, via Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        from frametree.xnat import Xnat

        # Load existing store spec
        xnat_store = Xnat.load('xnat-central')

        # Partition dataset into training and test
        training = xnat_store.define(id='MYXNATPROJECT', include={'member': range(1, 81)})
        test = xnat_store.define(id='MYXNATPROJECT', include={'member': range(81, 101)})

        # Save to the dataset
        training.save("training")
        test.save("test")


.. _FrameTree: https://frametree.readthedocs.io
.. _XNAT: https://xnat.org
.. _BIDS: https://bids.neuroimaging.io
.. _YAML: https://yaml.org
