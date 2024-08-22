Command-line interface
======================

FrameTree's command line interface is grouped into five categories, `store`,
`dataset`, `apply`, `derive`. Below these categories are the
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


Grid
----

Commands used to define and work with datasets

.. click:: frametree.core.cli.grid:define
   :prog: frametree define

.. click:: frametree.core.cli.grid:add_source
   :prog: frametree add-source

.. click:: frametree.core.cli.grid:add_sink
   :prog: frametree add-sink

.. click:: frametree.core.cli.grid:missing_items
   :prog: frametree missing-items


Processing
----------

Commands for applying workflows and analyses to framesets and deriving derivative data

.. click:: frametree.core.cli.apply:apply
   :prog: frametree apply

.. click:: frametree.core.cli.derive:derive_column
   :prog: frametree derive

.. click:: frametree.core.cli.derive:menu
   :prog: frametree menu

.. click:: frametree.core.cli.derive:ignore_diff
   :prog: frametree ignore-diff
