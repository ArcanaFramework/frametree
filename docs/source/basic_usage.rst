
Basic usage
-----------

FrameTree is implemented in Python, and can be accessed either via it's
API or via the command-line interface (CLI).

The basic usage pattern is

#. Define a dataset to work with (see :ref:`datasets`)
#. Specify columns in the dataset to access data from and store data to (see :ref:`data_columns`)
#. Connect a `Pydra task or workflow <https://pydra.readthedocs.io/en/latest/components.html#dataflows-components-task-and-workflow>`_
#. Request derivative of the workflow

For example, given a dataset stored within the ``/data/my-dataset`` directory,
which contains two-layers of sub-directories, for subjects and sessions
respectively, FSL's Brain Extraction Tool (BET) can be executed
over all sessions using the command line interface

.. code-block:: console

    # Define dataset
    $ frametree dataset define '/data/my-project' subject session

    # Add source column to select a single T1-weighted image in each session subdirectory
    $ frametree dataset add-source '/data/my-dataset' T1w '.*mprage.*' medimage:Dicom --regex

    # Add sink column to store brain mask
    $ frametree dataset add-sink '/data/my-dataset' brain_mask medimage:NiftiGz

    # Apply BET Pydra task, connecting it between the source and sink
    $ frametree apply pipeline '/data/my-dataset' pydra.tasks.fsl.preprocess.bet:BET \
      --arg name brain_extraction \
      --input T1w in_file medimage:NiftiGz \
      --output brain_mask out_file .

    # Derive brain masks for all imaging sessions in dataset
    $ frametree derive column '/data/my-dataset' brain_maskAPI

This code will iterate over all imaging sessions in the directory tree, find and
convert T1-weighted images (which contain 'mprage' in their names) from
DICOM into the required gzipped NIfTI format, and then execute BET on the converted
files before they are saved back into the directory structure at
``<subject-id>/<session-id>/derivs/brain_mask.nii.gz``.

Alternatively, the same steps can be performed using the Python API:

.. code-block:: python

    # Import frametree module
    from pydra.tasks.fsl.preprocess.bet import BET
    from frametree.core import Dataset
    from frametree.medimage.data import Clinical
    from fileformats.medimage.data import Dicom, NiftiGz

    # Define dataset
    my_dataset = Dataset.load('/data/my-dataset', space=Clinical,
                              hierarchy=['subject', 'session'])

    # Add source column to select a single T1-weighted image in each session subdirectory
    my_dataset.add_source('T1w', '.*mprage.*', datatype=Dicom, is_regex=True)

    # Add sink column to store brain mask
    my_dataset.add_sink('brain_mask', 'derivs/brain_mask', datatype=NiftiGz)

    # Apply BET Pydra task, connecting it between the source and sink
    my_dataset.apply_pipeline(
        BET(name='brain_extraction'),
        inputs=[('T1w', 'in_file', NiftiGz)],  # Specify required input format
        outputs=[('brain_mask', 'out_file')])  # Output datatype matches stored so can be omitted

    # Derive brain masks for all imaging sessions in dataset
    my_dataset['brain_mask'].derive()


.. note::

    When referencing objects within the ``frametree`` package from the CLI such
    as file-datatype classes or data spaces (see :ref:`data_spaces`), the
    standard ``frametree.*.`` prefix can be dropped, e.g. ``medimage:Dicom``
    instead of the full path ``fileformats.medimage.data:Dicom``.
    Classes installed outside of the FrameTree package, should be referred to
    with their full import path.
