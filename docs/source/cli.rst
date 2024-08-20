Command-line interface
======================

FrameTree's command line interface is grouped into five categories, `store`,
`dataset`, `apply`, `derive`, and `deploy`. Below these categories are the
commands that interact with FrameTree's data model, processing and deployment
streams.


Store
-----

Commands used to access remove data stores and save them for further use

.. click:: frametree.core.cli.store:add
   :prog: frametree store add

.. click:: frametree.core.cli.store:rename
   :prog: frametree store rename

.. click:: frametree.core.cli.store:remove
   :prog: frametree store remove

.. click:: frametree.core.cli.store:refresh
   :prog: frametree store refresh

.. click:: frametree.core.cli.store:ls
   :prog: frametree store ls


Dataset
-------

Commands used to define and work with datasets

.. click:: frametree.core.cli.dataset:define
   :prog: frametree dataset define

.. click:: frametree.core.cli.dataset:add_source
   :prog: frametree dataset add-source

.. click:: frametree.core.cli.dataset:add_sink
   :prog: frametree dataset add-sink

.. click:: frametree.core.cli.dataset:missing_items
   :prog: frametree dataset missing-items


Apply
-----

Commands for applying workflows and analyses to datasets

.. click:: frametree.core.cli.apply:apply_pipeline
   :prog: frametree apply pipeline


.. click:: frametree.core.cli.apply:apply_analysis
   :prog: frametree apply analysis


Derive
-------

Commands for calling workflows/analyses to derive derivative data

.. click:: frametree.core.cli.derive:derive_column
   :prog: frametree derive column

.. click:: frametree.core.cli.derive:derive_output
   :prog: frametree derive output

.. click:: frametree.core.cli.derive:menu
   :prog: frametree derive menu

.. click:: frametree.core.cli.derive:ignore_diff
   :prog: frametree derive ignore-diff


Deploy
------

Commands for deploying frametree pipelines


.. click:: frametree.core.cli.deploy:build
   :prog: frametree deploy build

.. click:: frametree.core.cli.deploy:test
   :prog: frametree deploy test

.. click:: frametree.core.cli.deploy:make_docs
   :prog: frametree deploy docs

.. click:: frametree.core.cli.deploy:inspect_docker_exec
   :prog: frametree deploy inspect-docker
