
Columns
=======

The "columns" of a data frame are slices of comparable data items across each row, e.g.

* T1-weighted MR acquisition for each imaging session
* a genetic test for each subject
* an fMRI activation map derived for each study group.

.. TODO: visualisation of data frame

A data frame is defined by adding "source" columns to access existing
(typically acquired) data, and "sink" columns to define where
derivatives will be stored within the data tree. The "row frequency" argument
of the column (e.g. per 'session', 'subject', etc...) specifies which data frame
the column belongs to. The datatype of a column's member items (see :ref:`Entries`)
must be consistent and is also specified when the column is created.

The data items (e.g. files, scans) within a source column do not need to have
consistent labels throughout the dataset although it makes it easier where possible.
To handle the case of inconsistent labelling, source columns can match single items
in each row of the frame based on several criteria:

* **path** - label for the file-group or field
    * scan type for XNAT stores
    * relative file path from row sub-directory for file-system/BIDS stores
    * is treated as a regular-expression if the `is_regex` flag is set.
* **quality threshold** - the minimum quality for the item to be included
    * only applicable for XNAT_ stores, where the quality can be set by UI or API
* **header values** - header values are sometimes needed to distinguish file
    * only available for selected item formats such as :class:`.medimage.Dicom`
* **order** - the order that an item appears the data row
    * e.g. first T1-weighted scan that meets all other criteria in a session

If no items, or multiple items are matched, then an error is raised. The *order*
flag, can be used to select one of muliple valid options.

The ``path`` argument provided to sink columns defines where derived data will
be stored within the dataset:

* the resource name for XNAT stores.
* the relative path to the target location for file-system stores

Each column is assigned a name when it is created, which is used when
connecting pipeline inputs and outputs to the dataset and accessing the data directly.
The column name is used as the default value for the path of sink columns.

Use the ':ref:`frametree add-source`' and ':ref:`frametree add-sink`'
commands to add columns to a dataset using the CLI.

.. code-block:: console

    $ frametree add-source 'xnat-central//MYXNATPROJECT' T1w \
      medimage/dicom-series --path '.*t1_mprage.*' \
      --order 1 --quality usable --regex

    $ frametree add-sink '/data/imaging/my-project' fmri_activation_map \
      medimage/nifti-gz --row-frequency group


Alternatively via the Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        from frametree.common import Clinical
        from fileformats.medimage import DicomSeries, NiftiGz

        xnat_dataset.add_source(
            name='T1w',
            path=r'.*t1_mprage.*'
            datatype=DicomSeries,
            order=1,
            quality_threshold='usable',
            is_regex=True
        )

        fs_dataset.add_sink(
            name='brain_template',
            datatype=NiftiGz,
            row_frequency='group'
        )

Once defined, the column data can be conveniently accessed and manipulated via the Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        import matplotlib.pyplot as plt
        from frametree.core import FrameSet

        # Get a column containing all T1-weighted MRI images across the dataset
        xnat_dataset = FrameSet.load('xnat-central//MYXNATPROJECT')
        t1w = xnat_dataset['T1w']

        # Plot a slice of the image data from a Subject sub01's imaging session
        # at visit Timepoint TP2. (Note: such data access is only available for selected
        # data formats that have convenient Python readers)
        plt.imshow(t1w['TP2', 'sub01'].data[:, :, 30])


    NB: one of the main benefits of using datasets in BIDS_ datatype is that the names
    and file formats of the data are strictly defined. This allows the :class:`.Bids`
    data store object to automatically add sources to the dataset when it is
    initialised.

    .. code-block:: python

        from frametree.bids import Bids

        bids_dataset = Bids().dataset(
            id='/data/openneuro/ds00014')

        # Print dimensions of T1-weighted MRI image for Subject 'sub01'
        print(bids_dataset['T1w']['sub01'].header['dim'])


Entries
-------

Atomic entries within a dataset contain either file-based data or text/numeric fields.
In FrameTree, these data items are represented using `fileformats <https://arcanaframework.github.io/fileformats/>`__
classes, :class:`.FileSet`, (i.e. single files, files + header/side-cars or directories)
and :class:`.Field` (e.g. integer, decimal, text, boolean, or arrays thereof), respectively.

Data types/file formats can be specified in the CLI using their `MIME-type <https://www.iana.org/assignments/media-types/media-types.xhtml>`__
or a "MIME-like" string, where their type name and registry correspond directly to the
fileformats to the fileformats sub-package/class name are specified in the CLI by *<module-path>/<class-name>*,
in "kebab case" e.g. ``mediamge/nifti-gz``.

Some frequently used data types are

* ``text/plain`` - a text file
* ``application/zip`` - a zip archive
* ``application/json`` - a JSON file
* ``generic/file`` - a single file of any type
* ``generic/directory`` - a directory containing any files/sub-directories
* ``medimage/nifti-gz-x`` - a gzipped NIfTI file with a BIDS_ JSON side-car (produced by Dcm2Niix_)
* ``medimage/dicom-series`` - a directory containing a series of DICOM files
* ``field/text`` - a text field
* ``field/decimal`` - a decimal field

The corresponding Python classes are:

.. toggle:: Show/Hide Python Code Example

    * :class:`fileformats.text.Plain`
    * :class:`fileformats.application.Zip`
    * :class:`fileformats.application.Json`
    * :class:`fileformats.generic.File`
    * :class:`fileformats.generic.Directory`
    * :class:`fileformats.medimage.DicomSeries`
    * :class:`fileformats.medimage.NiftiGz`
    * :class:`fileformats.field.Text`
    * :class:`fileformats.field.Decimal`

"Extras" packages for some of the file formats may provide converters to alternative
formats (e.g. ``medimage/dicom-series`` to ``medimage/nifti-gz-x`` via Dcm2Niix_).
They may also contain methods for accessing the headers and the contents of files
where applicable.

Where a converter is specified from an alternative file format is specified,
FrameTree will automatically run the conversion between the format required by
a pipeline and that stored in the data store. See FileFormats_ for detailed
instructions on how to specify new file formats and converters between them.



.. _XNAT: https://xnat.org
.. _FileFormats: https://arcanaframework.github.io/fileformats/
.. _BIDS: https://bids.neuroimaging.io
.. _Dcm2Niix: https://github.com/rordenlab/dcm2niix
