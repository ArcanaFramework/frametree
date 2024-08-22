Command-line interface
======================

FrameTree's command line interface allows you to create stores and frame sets, add
source and sink columns, apply pipelines and create derivatives. It can be grouped
into three sections, *Store management*, *frame specification*, and *processing*.


Store management
----------------

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


Frame specification
-------------------

Commands used to define and work with datasets

.. click:: frametree.core.cli.frameset:define
   :prog: frametree define

.. click:: frametree.core.cli.frameset:add_source
   :prog: frametree add-source

.. click:: frametree.core.cli.frameset:add_sink
   :prog: frametree add-sink

.. click:: frametree.core.cli.frameset:missing_items
   :prog: frametree missing-items


Processing
----------

Commands for applying workflows and analyses to framesets and generate derivative data

.. click:: frametree.core.cli.apply:apply
   :prog: frametree apply

.. click:: frametree.core.cli.derive:derive_column
   :prog: frametree derive

.. click:: frametree.core.cli.derive:menu
   :prog: frametree menu

.. click:: frametree.core.cli.derive:ignore_diff
   :prog: frametree ignore-diff
