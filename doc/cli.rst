perf commands
=============

Commands:

* :ref:`show <show_cmd>`
* :ref:`compare and compare_to <compare_cmd>`
* :ref:`stats <stats_cmd>`
* :ref:`dump <dump_cmd>`
* :ref:`hist <hist_cmd>`
* :ref:`convert <convert_cmd>`
* :ref:`metadata <metadata_cmd>`
* :ref:`timeit <timeit_cmd>`
* :ref:`slowest <slowest_cmd>`


The Python perf module comes with a ``pyperf`` program which includes different
commands. If for some reasons, ``pyperf`` program cannot be used, ``python3 -m
perf ...`` can be used: it is the same, it's just longer to type :-) For
example, the ``-m perf ...`` syntax is preferred for ``timeit`` because this
command uses the running Python program.

General note: if a filename is ``-``, read the JSON content from stdin.

.. _show_cmd:

show
----

Show benchmarks of one or multiple benchmark suites::

    python3 -m perf show
        [-q/--quiet]
        [-d/--dump]
        [-m/--metadata]
        |-g/--hist] [-t/--stats]
        [-b NAME/--name NAME]
        filename.json [filename2.json ...]

* ``--quiet`` enables the quiet mode
* ``--dump`` displays the benchmark run results,
  see :ref:`perf dump <dump_cmd>` command
* ``--metadata`` displays benchmark metadata: see :ref:`perf metadata
  <metadata_cmd>` command
* ``--hist`` renders an histogram of samples, see :ref:`perf hist <hist_cmd>`
  command
* ``--stats`` displays statistics (min, max, ...), see :ref:`perf stats
  <stats_cmd>` command
* ``--name NAME`` only displays the benchmark called ``NAME``

.. _show_cmd_metadata:

Example::

    $ python3 -m perf show telco.json
    Median +- std dev: 24.6 ms +- 0.2 ms

Example with metadata::

    $ python3 -m perf show telco.json --metadata
    Metadata:
    - aslr: Full randomization
    - cpu_affinity: 1 (isolated)
    - cpu_count: 2
    - cpu_model_name: Intel(R) Core(TM) i7-3520M CPU @ 2.90GHz
    - perf_version: 0.7
    ...

    Median +- std dev: 24.6 ms +- 0.2 ms

.. _compare_cmd:

compare and compare_to
----------------------

Compare benchmark suites, compute the minimum of each benchmark to use it as
the reference::

    python3 -m perf
        [-v/--verbose] [-m/--metadata]
        compare reference.json filename.json filename2.json [filename3.json ...]

Compare benchmark suites, use the first file as the reference::

    python3 -m perf
        [-v/--verbose] [-q/--quiet]
        [-G/--group-by-speed]
        [--min-speed=MIN_SPEED]
        compare_to reference.json changed.json [changed2.json ...]

Example::

    $ python3 -m perf compare py2.json py3.json
    Reference (best): py2

    Average: [py2] 46.3 ns +- 2.2 ns -> [py3] 56.3 ns +- 2.5 ns: 1.2x slower
    Significant (t=-25.90)

Options:

* ``--group-by-speed``: group results by "Slower", "Faster" and "Same speed"
* ``--min-speed``: Absolute minimum of speed in percent to consider that a
  benchmark is significant (default: 0%)


.. _stats_cmd:

stats
-----

Compute statistics on a benchmark result::

    python3 -m perf stats
        file.json [file2.json ...]

Example::

    $ python3 -m perf stats telco.json
    Raw sample minimum: 96.9 ms
    Raw sample maximum: 100 ms

    Number of runs: 40
    Total number of samples: 120
    Number of samples per run: 3
    Number of warmups per run: 1
    Loop iterations per sample: 4

    Minimum: 24.2 ms (-1%)
    Median +- std dev: 24.6 ms +- 0.2 ms
    Mean +- std dev: 24.6 ms +- 0.2 ms
    Maximum: 25.0 ms (+2%)

Values:

* `Median <https://en.wikipedia.org/wiki/Median>`_
* "std dev": `Standard deviation (standard error)
  <https://en.wikipedia.org/wiki/Standard_error>`_


.. _dump_cmd:

dump
----

Display the benchmark run results::

    python3 -m perf dump
        [-q/--quiet]
        [-v/--verbose]
        [--raw]
        file.json [file2.json ...]

Options:

* ``--quiet`` enables the quiet mode: hide warmup samples
* ``--verbose`` enables the verbose mode: show run metadata
* ``--raw`` displays raw samples rather than samples

Example::

    $ python3 -m perf dump telco.json
    Run 1/50: warmup (1): 24.9 ms; samples (3): 24.6 ms, 24.6 ms, 24.6 ms
    Run 2/50: warmup (1): 25.0 ms; samples (3): 24.8 ms, 24.8 ms, 24.6 ms
    Run 3/50: warmup (1): 24.6 ms; samples (3): 24.6 ms, 24.5 ms, 24.3 ms
    (...)
    Run 50/50: warmup (1): 24.8 ms; samples (3): 24.6 ms, 24.8 ms, 24.8 ms

Example in verbose mode::

    $ python3 -m perf dump telco.json -v
    Metadata:
      cpu_count: 2
      cpu_model_name: Intel(R) Core(TM) i7-3520M CPU @ 2.90GHz
      hostname: selma
      loops: 4
      name: telco
      ...

    Run 1: warmup (1): 24.7 ms; samples (3): 24.5 ms, 24.5 ms, 24.5 ms
      cpu_freq: 1=3588 MHz
      date: 2016-07-17T22:50:27
      load_avg_1min: 0.12
    Run 2: warmup (1): 25.0 ms; samples (3): 24.8 ms, 24.6 ms, 24.8 ms
      cpu_freq: 1=3586 MHz
      date: 2016-07-17T22:50:27
      load_avg_1min: 0.12
    ...


.. _hist_cmd:

hist
----

Render an histogram in text mode::

    python3 -m perf hist
        [-n BINS/--bins=BINS] [--extend]
        filename.json [filename2.json ...]

* ``--bins`` is the number of histogram bars. By default, it renders up to 25
  bars, or less depending on the terminal size.
* ``--extend``: don't limit to 80 colums x 25 lines but fill the whole
  terminal if it is wider.

If multiple files are used, the histogram is normalized on the minimum and
maximum of all files to be able to easily compare them.

Example::

    $ python3 -m perf hist telco.json
    26.4 ms:  1 ##
    26.4 ms:  1 ##
    26.4 ms:  2 #####
    26.5 ms:  1 ##
    26.5 ms:  1 ##
    26.5 ms:  4 #########
    26.6 ms:  8 ###################
    26.6 ms:  6 ##############
    26.7 ms: 11 ##########################
    26.7 ms: 13 ##############################
    26.7 ms: 18 ##########################################
    26.8 ms: 21 #################################################
    26.8 ms: 34 ###############################################################################
    26.8 ms: 26 ############################################################
    26.9 ms: 11 ##########################
    26.9 ms: 14 #################################
    27.0 ms: 17 ########################################
    27.0 ms: 14 #################################
    27.0 ms: 10 #######################
    27.1 ms: 10 #######################
    27.1 ms:  7 ################
    27.1 ms: 12 ############################
    27.2 ms:  5 ############
    27.2 ms:  2 #####
    27.3 ms:  0 |
    27.3 ms:  1 ##

See `Gaussian function <https://en.wikipedia.org/wiki/Gaussian_function>`_ and
`Probability density function (PDF)
<https://en.wikipedia.org/wiki/Probability_density_function>`_.


.. _convert_cmd:

convert
-------

Convert or modify a benchmark suite::

    python3 -m perf convert
        [--include-benchmark=NAME]
        [--exclude-benchmark=NAME]
        [--include-runs=RUNS]
        [--remove-outliers]
        [--indent]
        [--remove-warmups]
        [--add=FILE]
        [--extract-metadata=NAME]
        [--remove-all-metadata]
        [--update-metadata=METADATA]
        input_filename.json
        (-o output_filename.json/--output=output_filename.json
        | --stdout)

Operations:

* ``--include-benchmark=NAME`` only keeps the benchmark called ``NAME``
* ``--exclude-benchmark=NAME`` removes the benchmark called ``NAME``
* ``--include-runs=RUNS`` only keeps benchmark runs ``RUNS``. ``RUNS`` is a
  list of runs separated by commas, it can include a range using format
  ``first-last`` which includes ``first`` and ``last`` values. Example:
  ``1-3,7`` (1, 2, 3, 7).
* ``--remove-outliers`` removes "outlier runs", runs which contains at least
  one sample which is not in the range ``[median - 5%; median + 5%]``.
  See `Outlier (Wikipedia) <https://en.wikipedia.org/wiki/Outlier>`_.
* ``--remove-warmups``: remove warmup samples
* ``--add=FILE``: Add benchmark runs of benchmark *FILE*
* ``--extract-metadata=NAME``: Use metadata *NAME* as the new run values
* ``--remove-all-metadata``: Remove all benchmarks metadata except ``name`` and
  ``unit``.
* ``--update-metadata=METADATA``: Update metadata: ``METADATA`` is a
  comma-separated list of ``KEY=VALUE``

Options:

* ``--indent``: Indent JSON (rather using compact JSON)
* ``--stdout`` writes the result encoded as JSON into stdout


.. _metadata_cmd:

metadata
--------

Collect metadata::

    python3 -m perf metadata
        [--affinity=CPU_LIST]

Options:

* ``--affinity=CPU_LIST``: Specify CPU affinity. By default, use isolate CPUs.
  See :ref:`CPU pinning and CPU isolation <pin-cpu>`.

Example::

    $ python3 -m perf metadata
    Metadata:
    - aslr: Full randomization
    - cpu_config: 0-3=driver:intel_pstate, intel_pstate:turbo, governor:powersave
    - cpu_count: 4
    - cpu_freq: 0=2181 MHz, 1=2270 MHz, 2=2191 MHz, 3=2198 MHz
    - cpu_model_name:  Intel(R) Core(TM) i7-3520M CPU @ 2.90GHz
    - cpu_temp: coretemp:Physical id 0=51 C, coretemp:Core 0=50 C, coretemp:Core 1=51 C
    - date: 2016-07-18T22:57:06
    - hostname: selma
    - load_avg_1min: 0.02
    - perf_version: 0.8
    - platform: Linux-4.6.3-300.fc24.x86_64-x86_64-with-fedora-24-Twenty_Four
    - python_executable: /usr/bin/python3
    - python_implementation: cpython
    - python_version: 3.5.1 (64bit)
    - timer: clock_gettime(CLOCK_MONOTONIC), resolution: 1.00 ns


.. _timeit_cmd:

timeit
------

Usage
^^^^^

``perf timeit`` usage::

    python3 -m perf timeit [options] [-s SETUP] stmt [stmt ...]

See :ref:`TextRunner CLI <textrunner_cli>` for options.

.. note::
   timeit ``-n`` (number) and ``-r`` (repeat) options become ``-l`` (loops) and
   ``-n`` (runs) in perf timeit.

Example
^^^^^^^

Example::

    $ python3 -m perf timeit '" abc ".strip()
    .........................
    Median +- std dev: 113 ns +- 2 ns

Verbose example::

    $ python3 -m perf timeit --rigorous --hist --dump --metadata '" abc ".strip()'
    ........................................
    Metadata:
    - cpu_model_name: Intel(R) Core(TM) i7-3520M CPU @ 2.90GHz
    - loops: 2^20
    - platform: Linux-4.6.3-300.fc24.x86_64-x86_64-with-fedora-24-Twenty_Four
    - python_version: 3.5.1 (64bit)
    - timeit_setup: 'pass'
    - timeit_stmt: '" abc ".strip()'
    - timer: clock_gettime(CLOCK_MONOTONIC), resolution: 1.00 ns
    ...

    Run 1: warmup (1): 135 ns (+18%); samples (3): 112 ns, 112 ns, 114 ns
    Run 2: warmup (1): 122 ns (+7%); samples (3): 121 ns (+6%), 112 ns, 112 ns
    Run 3: warmup (1): 112 ns; samples (3): 112 ns, 112 ns, 112 ns
    ...
    Run 40: warmup (1): 117 ns; samples (3): 114 ns, 137 ns (+20%), 123 ns (+8%)

    107 ns:  8 ###########
    111 ns: 59 ###############################################################################
    116 ns: 21 ############################
    120 ns: 10 #############
    125 ns:  9 ############
    129 ns:  3 ####
    133 ns:  4 #####
    138 ns:  1 #
    142 ns:  1 #
    147 ns:  1 #
    151 ns:  0 |
    156 ns:  0 |
    160 ns:  0 |
    165 ns:  2 ###
    169 ns:  0 |
    174 ns:  0 |
    178 ns:  0 |
    182 ns:  0 |
    187 ns:  0 |
    191 ns:  0 |
    196 ns:  1 #

    WARNING: the benchmark seems unstable, the standard deviation is high (stdev/median: 11%)
    Try to rerun the benchmark with more runs, samples and/or loops

    Median +- std dev: 114 ns +- 12 ns


timeit versus perf timeit
^^^^^^^^^^^^^^^^^^^^^^^^^

The timeit module of the Python standard library has multiple issues:

* It displays the minimum
* It only runs the benchmark 3 times using a single process (1 run, 3 samples)
* It disables the garbage collector

perf timeit is more reliable and gives a result more representative of a real
use case:

* It displays the average and the standard deviation
* It runs the benchmark in multiple processes
* By default, it skips the first sample in each process to warmup the benchmark
* It does not disable the garbage collector

If a benchmark is run using a single process, we get the performance for one
specific case, whereas many parameters are random:

* Since Python 3, the hash function is now randomized and so the number of
  hash collision in dictionaries is different in each process
* Linux uses address space layout randomization (ASLR) by default and so
  the performance of memory accesses is different in each process

See the :ref:`Minimum versus average and standard deviation <min>` section.


.. _slowest_cmd:

slowest
-------

Display the 5 benchmarks which took the most time to be run. This command
should not be used to compare performances, but only to find "slow" benchmarks
which makes running benchmarks taking too long.

Options:

* ``-n``: Number of slow benchmarks to display (default: ``5``)

