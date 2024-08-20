
Installation
============

Software requirements
---------------------

FrameTree requires a recent version of Python (>=3.8) to run. So you may
need to upgrade your Python version before it is installed. The best way
to install Python depends on your OS:

* Windows - it is very strongly recommended to use Anaconda_ to install Python because it will manage C dependencies as well
* Mac - either `Homebrew <https://brew.sh/>`_ or Anaconda_ are good options
* Linux - the native package manager should work ok unless you are using an old Linux distribution that doesn't support Python 3.8, in which case `Linuxbrew <https://docs.brew.sh/Homebrew-on-Linux>`_ is a good option


To deploy FrameTree pipelines to Docker_ images XNAT's container service,
Docker_ needs to be installed. Please see the Docker_ docs for how to do this,
`<https://docs.docker.com/engine/install/>`_ for your system.

One of the main strengths of Pydra is the ability to link 3rd party tools
together into coherent workflows. 3rd party tools are best run within software
containers (e.g. Docker_ or Singularity_), but in cases where that isn't possible
(i.e. when nested within other containers without access to Docker socket or
on some high-performance computing clusters) you will obviously need to have
installed these dependencies on the system and ensure they are on the `system
path <https://learn.sparkfun.com/tutorials/configuring-the-path-system-variable/all>`_.

Two command-line tools that the the `frametree-medimage` sub-package uses
for implicit file-format conversions are

* `Dcm2Niix <https://github.com/rordenlab/dcm2niix>`_
* `Mrtrix3 <https://mrtrix.readthedocs.io/en/latest/index.html>`_

Both these packages can be installed using Home/LinuxBrew (you will need to tap
``MRtrix3/mrtrix3``) and Anaconda_ (use the ``conda-forge`` and ``mrtrix3``
repositories for Dcm2Niix and MRtrix3 respectively).


Python
------

FrameTree can be installed along with its Python dependencies from the
`Python Package Index <http://pypi.org>`_ using *Pip3*

.. code-block:: console

    $ pip3 install frametree



.. _Pydra: http://pydra.readthedocs.io
.. _Anaconda: https://www.anaconda.com/products/individual
.. _Docker: https://www.docker.com/
.. _Singularity: https://sylabs.io/guides/3.0/user-guide/index.html
