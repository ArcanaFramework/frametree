Tree Stores
===========

Support for different tree-like storage systems (e.g. plain file systems, XNAT_) and
structures (e.g. BIDS_) is provided by sub-classes of :class:`.Store`. Tree store classes
not only encapsulate where the data are stored, e.g. on local disk or remote repository,
but also how data are accessed, e.g. whether to assume that they are in BIDS format, or
whether files in an XNAT archive mount can be accessed directly (i.e. as exposed to the
container service) or only via the API.

There are currently four supported store classes in the common, `frametree-bids` and `frametree-xnat`
packages

* :class:`.FileSystem` - access data organised within an arbitrary directory tree on the file system
* :class:`.Bids` - access data on file systems organised in the `Brain Imaging Data Structure (BIDS) <https://bids.neuroimaging.io/>`__
* :class:`.Xnat` - access data stored in XNAT_ repositories vi its REST API
* :class:`.XnatViaCS` - access data stored in XNAT_ via its `container service <https://wiki.xnat.org/container-service/using-the-container-service-122978908.html>`_

For instructions on how to add support for new systems see :ref:`alternative_backends`.

To configure access to a store via the CLI use the ':ref:`frametree store add`' command.
The store type is specified by the path to the data store sub-class,
*<module-path>:<class-name>*,  e.g. ``frametree.xnat:Xnat``.
However, if the store is in a submodule of ``frametree`` then that
prefix can be dropped for convenience, e.g. ``xnat:Xnat``, and if there is only one store
in that module, just the module name, e.g. ``bids``.

.. code-block:: console

    $ frametree store add xnat xnat-central https://central.xnat.org \
      --user user123 --cache /work/xnat-cache
    Password:

This command will create a YAML configuration file for the store in the
`~/.frametree/stores/` directory. Authentication tokens are saved in the config
file instead of usernames and passwords, and will need to be
refreshed when they expire (see ':ref:`frametree store refresh`').

The CLI also contains commands for working with store entries that have already
been created

* :ref:`frametree store ls` - list saved stores
* :ref:`frametree store rename` - rename a store
* :ref:`frametree store remove` - remove a store
* :ref:`frametree store refresh` - refreshes authentication tokens saved for the store

Alternatively, data stores can be configured via the Python API by initialising the
data store classes directly.

.. code-block:: python

    import os
    from frametree.xnat import Xnat

    # Initialise the data store object
    xnat_store = Xnat(
        server='https://central.xnat.org',
        user='user123',
        password=os.environ['XNAT_PASS'],
        cache_dir='/work/xnat-cache'
    )

    # Save it to the configuration file stored at '~/.frametree/stores.yaml' with
    # the nickname 'xnat-central'
    xnat_store.save('xnat-central')

    # Reload store from configuration file
    reloaded = Store.load('xnat-central')

.. note::

    Data stores that don't require any parameters such as :class:`.FileSystem` and
    :class:`.Bids` don't need to be configured and can be accessed via their aliases,
    ``file`` and ``bids`` when defining a dataset, e.g. ``bids///path/to/bids/dataset``.


.. _XNAT: https://xnat.org
.. _BIDS: https://bids.neuroimaging.io
