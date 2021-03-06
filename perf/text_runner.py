from __future__ import division, print_function, absolute_import

import argparse
import errno
import math
import os
import subprocess
import sys

import six

import perf
from perf._cli import display_run, display_benchmark
from perf._utils import (format_timedelta, format_number,
                         format_cpu_list, parse_cpu_list,
                         get_isolated_cpus, set_cpu_affinity,
                         MS_WINDOWS)

try:
    # Optional dependency
    import psutil
except ImportError:
    psutil = None


def _run_cmd(args, env):
    proc = subprocess.Popen(args,
                            universal_newlines=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=env)

    try:
        stdout, stderr = proc.communicate()
    except:
        proc.stdout.close()
        proc.stderr.close()
        try:
            proc.kill()
        except OSError:
            # process already exited
            pass
        proc.wait()
        raise

    if proc.returncode:
        sys.stdout.write(stdout)
        sys.stdout.flush()
        sys.stderr.write(stderr)
        sys.stderr.flush()
        raise RuntimeError("%s failed with exit code %s"
                           % (args[0], proc.returncode))

    return stdout


class TextRunner:
    # Default parameters are chosen to have approximatively a run of 0.5 second
    # and so a total duration of 5 seconds by default
    def __init__(self, name, samples=None, warmups=None, processes=None,
                 loops=0, min_time=0.1, max_time=1.0, metadata=None,
                 inner_loops=None, _argparser=None):
        if not name:
            raise ValueError("name must be a non-empty string")

        has_jit = perf.python_has_jit()
        if not samples:
            if has_jit:
                # Since PyPy JIT has less processes:
                # run more samples per process
                samples = 10
            else:
                samples = 3
        if not warmups:
            if has_jit:
                # PyPy JIT needs a longer warmup (at least 1 second)
                warmups = int(math.ceil(1.0 / min_time))
            else:
                warmups = 1
        if not processes:
            if has_jit:
                # Use less processes than non-JIT, because JIT requires more
                # warmups and so each worker is slower
                processes = 6
            else:
                processes = 20

        self.name = name
        if metadata is not None:
            self.metadata = metadata
        else:
            self.metadata = {}

        # result of argparser.parse_args()
        self.args = None

        # callback used to prepare command line arguments to spawn a worker
        # child process. The callback is called with prepare(runner, args).
        # args must be modified in-place.
        self.prepare_subprocess_args = None

        # Command list arguments to call the program:
        # (sys.executable, sys.argv[0]) by default. For example,
        # "python3 -m perf timeit" sets program_args to
        # (sys.executable, '-m', 'perf', 'timeit').
        self.program_args = (sys.executable, sys.argv[0])

        # Number of inner-loops of the sample_func for bench_sample_func()
        self.inner_loops = inner_loops

        def strictly_positive(value):
            value = int(value)
            if value <= 0:
                raise ValueError("value must be > 0")
            return value

        def positive_or_nul(value):
            value = int(value)
            if value < 0:
                raise ValueError("value must be >= 0")
            return value

        def comma_separated(values):
            values = [value.strip() for value in values.split(',')]
            return list(filter(None, values))

        if _argparser is not None:
            parser = _argparser
        else:
            parser = argparse.ArgumentParser()
        parser.description = 'Benchmark'
        parser.add_argument('--rigorous', action="store_true",
                            help='Spend longer running tests '
                                 'to get more accurate results')
        parser.add_argument('--fast', action="store_true",
                            help='Get rough answers quickly')
        parser.add_argument("--debug-single-sample", action="store_true",
                            help="Debug mode, only collect a single sample")
        parser.add_argument('-p', '--processes',
                            type=strictly_positive, default=processes,
                            help='number of processes used to run benchmarks '
                                 '(default: %s)' % processes)
        parser.add_argument('-n', '--samples', dest="samples",
                            type=strictly_positive, default=samples,
                            help='number of samples per process (default: %s)'
                                 % samples)
        parser.add_argument('-w', '--warmups', dest="warmups",
                            type=positive_or_nul, default=warmups,
                            help='number of skipped samples per run used '
                                 'to warmup the benchmark (default: %s)'
                                 % warmups)
        parser.add_argument('-l', '--loops',
                            type=positive_or_nul, default=loops,
                            help='number of loops per sample, 0 means '
                                 'automatic calibration (default: %s)'
                            % loops)
        parser.add_argument('-v', '--verbose', action="store_true",
                            help='enable verbose mode')
        parser.add_argument('-q', '--quiet', action="store_true",
                            help='enable quiet mode')
        parser.add_argument('--stdout', action='store_true',
                            help='write results encoded to JSON into stdout')
        parser.add_argument('-o', '--output', metavar='FILENAME',
                            help='write results encoded to JSON into FILENAME')
        parser.add_argument('--append', metavar='FILENAME',
                            help='append results encoded to JSON into FILENAME')
        parser.add_argument('--min-time', type=float, default=min_time,
                            help='Minimum duration in seconds of a single '
                                 'sample, used to calibrate the number of '
                                 'loops (default: %s)'
                            % format_timedelta(min_time))
        parser.add_argument('--worker', action="store_true",
                            help='worker process, run the benchmark')
        parser.add_argument('-d', '--dump', action="store_true",
                            help='display benchmark run results')
        parser.add_argument('--metadata', '-m', action="store_true",
                            help='show metadata')
        parser.add_argument('--hist', '-g', action="store_true",
                            help='display an histogram of samples')
        parser.add_argument('--stats', '-t', action="store_true",
                            help='display statistics (min, max, ...)')
        parser.add_argument("--affinity", metavar="CPU_LIST", default=None,
                            help='Specify CPU affinity for worker processes. '
                                 'This way, benchmarks can be forced to run '
                                 'on a given set of CPUs to minimize run to '
                                 'run variation. By default, worker processes '
                                 'are pinned to isolate CPUs if isolated CPUs '
                                 'are found.')
        parser.add_argument("--inherit-environ", metavar='VARS',
                            type=comma_separated,
                            help='Comma-separated list of environment '
                                 'variables inherited by worker child '
                                 'processes.')

        memory = parser.add_mutually_exclusive_group()
        memory.add_argument('--tracemalloc', action="store_true",
                            help='Trace memory allocations using tracemalloc')
        memory.add_argument('--track-memory', action="store_true",
                            help='Track memory usage using a thread')

        self.argparser = parser

    def _process_args(self):
        args = self.args

        if args.quiet:
            args.verbose = False

        nprocess = self.argparser.get_default('processes')
        nsamples = self.argparser.get_default('samples')
        if args.rigorous:
            args.processes = nprocess * 2
            # args.samples = nsamples * 5 // 3
        elif args.fast:
            # use at least 3 processes to benchmark 3 different (randomized)
            # hash functions
            args.processes = max(nprocess // 2, 3)
            args.samples = max(nsamples * 2 // 3, 2)
        elif args.debug_single_sample:
            args.processes = 1
            args.warmups = 0
            args.samples = 1
            args.loops = 1
            args.min_time = 1e-9

        filename = args.output
        if filename and os.path.exists(filename):
            print("ERROR: The JSON file %r already exists" % filename)
            sys.exit(1)

        if args.tracemalloc:
            try:
                import tracemalloc   # noqa
            except ImportError as exc:
                print("ERROR: fail to import tracemalloc: %s" % exc)
                sys.exit(1)

        if args.track_memory:
            if MS_WINDOWS:
                from perf._win_memory import check_tracking_memory
            else:
                from perf._memory import check_tracking_memory
            err_msg = check_tracking_memory()
            if err_msg:
                print("ERROR: unable to track the memory usage "
                      "(--track-memory): %s" % err_msg)
                sys.exit(1)

    def parse_args(self, args=None):
        if self.args is None:
            self.args = self.argparser.parse_args(args)
            self._process_args()
        return self.args

    def _stream(self):
        return sys.stderr if self.args.stdout else sys.stdout

    def _range(self):
        for warmup in six.moves.xrange(self.args.warmups):
            yield (True, 1 + warmup)
        for run in six.moves.xrange(self.args.samples):
            yield (False, 1 + run)

    def _cpu_affinity(self):
        stream = self._stream()

        cpus = self.args.affinity
        if not cpus:
            # --affinity option is not set: detect isolated CPUs
            isolated = True
            cpus = get_isolated_cpus()
            if not cpus:
                # no isolated CPUs or unable to get the isolated CPUs
                return
        else:
            isolated = False
            cpus = parse_cpu_list(cpus)

        if set_cpu_affinity(cpus):
            if self.args.verbose:
                if isolated:
                    text = ("Pin process to isolated CPUs: %s"
                            % format_cpu_list(cpus))
                else:
                    text = ("Pin process to CPUs: %s"
                            % format_cpu_list(cpus))
                print(text, file=stream)

            if isolated:
                self.args.affinity = format_cpu_list(cpus)
        else:
            if not isolated:
                print("ERROR: CPU affinity not available.", file=sys.stderr)
                print("Use Python 3.3 or newer, or install psutil dependency",
                      file=stream)
                sys.exit(1)
            else:
                print("WARNING: unable to pin worker processes to "
                      "isolated CPUs, CPU affinity not available", file=stream)
                print("Use Python 3.3 or newer, or install psutil dependency",
                      file=stream)

    def _run_bench(self, bench, sample_func, loops, nsample,
                   is_warmup=False, is_calibrate=False, calibrate=False):
        args = self.args
        stream = self._stream()
        if loops <= 0:
            raise ValueError("loops must be >= 1")

        if is_calibrate:
            sample_name = 'Calibration'
        elif is_warmup:
            sample_name = 'Warmup'
        else:
            sample_name = 'Sample'

        samples = []
        index = 1
        inner_loops = self.inner_loops or 1
        while True:
            if index > nsample:
                break

            raw_sample = sample_func(loops)
            raw_sample = float(raw_sample)
            sample = raw_sample / (loops * inner_loops)
            if is_warmup:
                value = raw_sample
            else:
                value = sample

            if not value and not(is_calibrate or is_warmup):
                raise ValueError("sample function returned zero")

            if is_warmup:
                samples.append((loops, value))
            else:
                samples.append(value)

            if args.verbose:
                text = bench.format_sample(sample)
                if is_warmup or is_calibrate:
                    text = ('%s (%s: %s)'
                            % (text,
                               format_number(loops, 'loop'),
                               bench.format_sample(raw_sample)))
                text = ("%s %s: %s"
                        % (sample_name, index, text))
                print(text, file=stream)

            if calibrate and raw_sample < args.min_time:
                loops *= 2
                if loops > 2 ** 32:
                    raise ValueError("error in calibration, loops is "
                                     "too big: %s" % loops)
                # need more samples for the calibration
                nsample += 1

            index += 1

        if args.verbose:
            print(file=stream)

        # Run collects metadata
        return (loops, samples)

    def _calibrate(self, bench, sample_func):
        return self._run_bench(bench, sample_func,
                               loops=1, nsample=1,
                               calibrate=True,
                               is_calibrate=True, is_warmup=True)

    def _worker(self, bench, sample_func):
        args = self.args
        loops = args.loops
        metadata = dict(self.metadata)
        start_time = perf.monotonic_clock()

        calibrate = (not loops)
        if calibrate:
            loops, calibrate_warmups = self._calibrate(bench, sample_func)
        else:
            if perf.python_has_jit():
                # With a JIT, continue to calibrate during warmup
                calibrate = True
            calibrate_warmups = None

        if args.track_memory:
            if MS_WINDOWS:
                from perf._win_memory import get_peak_pagefile_usage
            else:
                from perf._memory import PeakMemoryUsageThread
                mem_thread = PeakMemoryUsageThread()
                mem_thread.start()

        if args.tracemalloc:
            import tracemalloc
            tracemalloc.start()

        if args.warmups:
            loops, warmups = self._run_bench(bench, sample_func, loops,
                                             args.warmups,
                                             is_warmup=True, calibrate=calibrate)
        else:
            warmups = []
        if calibrate_warmups:
            warmups = calibrate_warmups + warmups
        loops, samples = self._run_bench(bench, sample_func, loops,
                                         args.samples)

        if args.tracemalloc:
            traced_peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()

            if not traced_peak:
                raise RuntimeError("tracemalloc didn't trace any Python "
                                   "memory allocation")

            # drop timings, replace them with the memory peak
            metadata['unit'] = 'byte'
            warmups = None
            samples = (float(traced_peak),)

        if args.track_memory:
            if MS_WINDOWS:
                mem_peak = get_peak_pagefile_usage()
            else:
                mem_thread.stop()
                mem_peak = mem_thread.peak_usage

            if not mem_peak:
                raise RuntimeError("failed to get the memory peak usage")

            # drop timings, replace them with the memory peak
            metadata['unit'] = 'byte'
            warmups = None
            samples = (float(mem_peak),)

        duration = perf.monotonic_clock() - start_time
        metadata['duration'] = duration
        metadata['name'] = self.name
        metadata['loops'] = loops
        if self.inner_loops is not None and self.inner_loops != 1:
            metadata['inner_loops'] = self.inner_loops

        run = perf.Run(samples, warmups=warmups, metadata=metadata)
        bench.add_run(run)
        self._display_result(bench, check_unstable=False)

        # Save loops into args
        args.loops = loops

    def _main(self, sample_func):
        args = self.parse_args()

        self._cpu_affinity()

        bench = perf.Benchmark()

        try:
            if args.worker:
                self._worker(bench, sample_func)
            else:
                self._spawn_workers(bench, sample_func)
        except KeyboardInterrupt:
            print("Interrupted: exit", file=sys.stderr)
            sys.exit(1)

        return bench

    def bench_sample_func(self, sample_func, *args):
        """"Benchmark sample_func(loops, *args)

        The function must return the total elapsed time, not the average time
        per loop iteration. The total elapsed time is required to be able
        to automatically calibrate the number of loops.

        perf.perf_counter() should be used to measure the elapsed time.
        """

        if not args:
            return self._main(sample_func)

        def wrap_sample_func(loops):
            return sample_func(loops, *args)

        return self._main(wrap_sample_func)

    def bench_func(self, func, *args):
        """"Benchmark func(*args)."""

        def sample_func(loops):
            # use fast local variables
            local_timer = perf.perf_counter
            local_func = func
            local_args = args

            if local_args:
                if loops != 1:
                    range_it = range(loops)

                    t0 = local_timer()
                    for _ in range_it:
                        local_func(*local_args)
                    dt = local_timer() - t0
                else:
                    t0 = local_timer()
                    local_func(*local_args)
                    dt = local_timer() - t0
            else:
                # fast-path when func has no argument: avoid the expensive
                # func(*args) argument unpacking

                if loops != 1:
                    range_it = range(loops)

                    t0 = local_timer()
                    for _ in range_it:
                        local_func()
                    dt = local_timer() - t0
                else:
                    t0 = local_timer()
                    local_func()
                    dt = local_timer() - t0

            return dt

        return self._main(sample_func)

    def _create_environ(self):
        env = {}

        # FIXME: copy the locale? LC_ALL, LANG, LC_*
        copy_env = ["PATH", "HOME", "TEMP", "COMSPEC", "SystemRoot"]
        if self.args.inherit_environ:
            copy_env.extend(self.args.inherit_environ)

        for name in copy_env:
            if name in os.environ:
                env[name] = os.environ[name]
        return env

    def _spawn_worker_suite(self):
        args = self.args

        cmd = []
        cmd.extend(self.program_args)
        cmd.extend(('--worker', '--stdout',
                     '--samples', str(args.samples),
                     '--warmups', str(args.warmups),
                     '--loops', str(args.loops),
                     '--min-time', str(args.min_time)))
        if args.verbose:
            cmd.append('-' + 'v' * args.verbose)
        if args.affinity:
            cmd.append('--affinity=%s' % args.affinity)
        if args.tracemalloc:
            cmd.append('--tracemalloc')
        if args.track_memory:
            cmd.append('--track-memory')

        if self.prepare_subprocess_args:
            self.prepare_subprocess_args(self, cmd)

        env = self._create_environ()
        stdout = _run_cmd(cmd, env=env)
        return perf.BenchmarkSuite.loads(stdout)

    def _spawn_worker_bench(self):
        suite = self._spawn_worker_suite()

        benchmarks = suite.get_benchmarks()
        if len(benchmarks) != 1:
            raise ValueError("worker produced %s benchmarks instead of 1"
                             % len(benchmarks))
        return benchmarks[0]

    def _display_result(self, bench, check_unstable=True):
        stream = self._stream()
        args = self.args

        # Display the average +- stdev
        if self.args.quiet:
            check_unstable = False
        display_benchmark(bench,
                          file=stream,
                          check_unstable=check_unstable,
                          metadata=args.metadata,
                          dump=args.dump,
                          stats=args.stats,
                          hist=args.hist)

        stream.flush()
        if args.append:
            perf.add_runs(args.append, bench)

        if args.stdout:
            try:
                bench.dump(sys.stdout)
            except IOError as exc:
                if exc.errno != errno.EPIPE:
                    raise
                # ignore broken pipe error

                # Close stdout to avoid the warning "Exception ignored in: ..."
                # at exit
                try:
                    sys.stdout.close()
                except IOError:
                    # close() is likely to fail with EPIPE (BrokenPipeError)
                    pass

        if args.output:
            bench.dump(args.output)

    def _spawn_workers(self, bench, sample_func):
        args = self.args
        verbose = args.verbose
        quiet = args.quiet
        stream = self._stream()
        nprocess = args.processes

        for process in range(nprocess):
            worker_bench = self._spawn_worker_bench()
            bench.add_runs(worker_bench)

            if verbose:
                run = bench.get_runs()[-1]
                run_index = '%s/%s' % (1 + process, nprocess)
                display_run(bench, run_index, run, file=stream)
            elif not quiet:
                print(".", end='', file=stream)
                stream.flush()

            if not args.loops:
                # Use the first worker to calibrate the benchmark. Use a worker
                # process rather than the main process because worker is a
                # little bit more isolated and so should be more reliable.
                first_run = worker_bench.get_runs()[0]
                args.loops = first_run._get_loops()
                if verbose:
                    print("Calibration: use %s loops" % format_number(args.loops),
                          file=stream)

        if not quiet:
            print(file=stream)

        self._display_result(bench)
