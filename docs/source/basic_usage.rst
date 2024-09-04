
Basic usage
-----------

FrameTree is implemented in Python, and can be accessed either via it's
API or via the command-line interface (CLI).

The basic usage pattern is

#. Save a connection details to a remote data store (if applicable) (see :ref:`Stores`)
#. Define a frame-set to work with (see :ref:`FrameSets`)
#. Specify columns in the dataset to access data from and store data to (see :ref:`columns`)
#. Connect a `Pydra task or workflow <https://pydra.readthedocs.io/en/latest/components.html#dataflows-components-task-and-workflow>`_
#. Request derivative of the workflow

If your dataset is stored in an XNAT repository, use the ``frametree store`` command to
save the the connection details

.. code-block:: console

    # Save a reference to an XNAT store in the $HOME/.frametree/stores.json file
    $ frametree store add my-xnat xnat https://xnat.example.com --user $XNAT_USER --password $XNAT_PASS

.. note::
    If your dataset is on your file system in a plain directory structure or BIDS layout
    you can skip this step.

For example, a dataset stored in the ``/data/my-dataset`` directory that contains
two-layers of sub-directories, for subjects and sessions respectively,
FSL's Brain Extraction Tool (BET) can be executed over all sessions using the command
line interface

.. code-block:: console

    $ # Define a frameset stored within a file-system directory '/data/my-dataset'
    $ # with a 2-layer directory structure: top level subject IDs, bottom level visit IDs
    $ frametree define /data/my-dataset subject visit --axes common/clinical

    $ # Add source column to select a single T1-weighted image in each session subdirectory
    $ frametree add-source /data/my-dataset T1w medimage/dicom-series --regex '.*mprage.*'

    $ # Add sink column to store brain mask
    $ frametree add-sink /data/my-dataset derivs/brain_mask medimage/nifti-gz

    $ # Apply BET Pydra task, connecting it between the source and sink
    $ frametree apply /data/my-dataset brain_extraction pydra.tasks.fsl.preprocess.bet:BET \
      --input T1w in_file \
      --output brain_mask out_file

    $ # Derive brain masks for all imaging sessions in dataset
    $ frametree derive /data/my-dataset derivs/brain_mask

This code will iterate over all imaging sessions in the directory tree, find and
convert T1-weighted images that contain 'mprage' in their names from
DICOM into the required gzipped NIfTI format, and then execute BET on the converted
files before they are saved back into the directory structure at
``<subject-id>/<session-id>/derivs/brain_mask.nii.gz``.

Alternatively via Python API:

.. toggle:: Show/Hide Python Code Example

    .. code-block:: python

        # Import frametree module
        from pydra.tasks.fsl.preprocess.bet import BET
        from frametree.core import FrameSet
        from frametree.common import Clinical
        from fileformats.medimage import DicomSeries, NiftiGz

        # Define a frameset stored within a file-system directory '/data/my-dataset'
        # with a 2-layer directory structure: top level subject IDs, bottom level visit IDs
        frames = FrameSet('/data/my-dataset', axes=Clinical, hierarchy=['subject', 'visit'])

        # Add source column to select a single T1-weighted image in each session subdirectory
        frames.add_source('T1w', '.*mprage.*', datatype=DicomSeries, is_regex=True)

        # Add sink column to store brain mask
        frames.add_sink('brain_mask', 'derivs/brain_mask', datatype=NiftiGz)

        # Apply BET Pydra task, connecting it between the source and sink
        frames.apply(
            'brain_extraction',
            BET,
            inputs=[('T1w', 'in_file', NiftiGz)],  # Specify required input format
            outputs=[('derivs/brain_mask', 'out_file')])  # Output datatype matches stored so can be omitted

        # Derive brain masks for all imaging sessions in dataset
        frames['derivs/brain_mask'].derive()
