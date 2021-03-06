# Copyright (C) 2012 Peter Teichman

import cStringIO as StringIO
import heapq
import logging
import operator
import tempfile

from . import varint

logger = logging.getLogger(__name__)


class MergeCounter(object):
    """Count unique string elements with tunable memory usage.

    MergeCounter automatically scales to lists of items that cannot
    fit into memory, writing counts to disk and yielding its results
    by merging the on-disk files.

    """
    def __init__(self, max_fds=32, max_len=4000000):
        """Init MergeCounter with tunable resource parameters.

        Args:
            max_fds: the maximum number of merge files to keep open
            max_len: the total length of strings stored before
                flushing counts to disk. This is an estimate of memory
                usage and not an accurate limit, as it doesn't include
                item counts or dict overhead.

        """

        self.max_fds = max_fds
        self.max_len = max_len

    def count(self, items):
        """Count string items.

        This method keeps an in-memory count of items until its size
        reaches max_len, then flushes the counts to a sorted overflow
        file on disk. It does this as many times as necessary, then
        merges the overflow files together in an iterator.

        Args:
            items: An iterable of (item, count) tuples in any order.

        Returns:
            An iterable of (item, count) tuples in lexically sorted
            order. The counts will be the sum of all counts from the
            input for the same item.

        """

        # Keep a running dict of counted items. Maps item -> integer count
        counts = {}

        # Track the file descriptors of temporary overflow files.
        fds = []

        left = self.max_len

        for item, count in items:
            if item not in counts:
                counts[item] = count
                left -= len(item)
            else:
                counts[item] += count

            if left < 0:
                # Write the current counts to an overflow
                # file. Overflow adds the new file to fds, and may
                # alter the others in the list if max_fds are open.
                logger.debug("overflow: %d items, %d bytes", len(counts),
                             self.max_len - left)
                self._overflow(counts, fds)

                counts.clear()
                left = self.max_len

        # Merge in-memory counts with the overflow files
        logger.debug("merging %d overflow files", len(fds))

        sources = [self.dict_counts(counts)]
        for fd in fds:
            sources.append(self.file_counts(fd))

        return self._sum_merge(*sources)

    def _overflow(self, counts, fds):
        fd = tempfile.TemporaryFile()

        source = self.dict_counts(counts)
        if len(fds) > self.max_fds:
            # If we've run out of file descriptors, merge the
            # in-memory counts with the oldest fd in the list.
            file_source = self.file_counts(fds.pop(0))
            source = self._sum_merge(source, file_source)

        write = fd.write
        for item, count in source:
            # Write the count and item length as varint-encoded integers.
            header = varint.encode((count, len(item)))

            write(header)
            write(item)

        fds.append(fd)

    def _sum_merge(self, *iters):
        # Merge together several already-sorted iterators, summing
        # the counts of any identical items.
        merge = heapq.merge(*iters)
        prev, accum = next(merge)

        for item, count in merge:
            if item != prev:
                yield prev, accum
                prev = item
                accum = count
            else:
                accum += count

        yield prev, accum

    def dict_counts(self, dictionary):
        """Return sorted item, count tuples from a dict of item -> count"""
        return sorted(dictionary.iteritems(), key=operator.itemgetter(0))

    def _read_varints(self, fd, buf, count):
        # varint decoding should be made stream based so this isn't
        # necessary.
        while count:
            byte = fd.read(1)
            if not byte:
                return

            buf.write(byte)

            if not ord(byte) & 0x80:
                count -= 1

    def file_counts(self, fd):
        """Return item, count tuples from an _overflow()-written file.

        These files have records serialized in the following format:

            [ header: varint count, varint item length ] [ item ]

        This generator yields (item, count) tuples from those records.
        """
        fd.seek(0)
        read = fd.read

        buf = StringIO.StringIO()
        while True:
            self._read_varints(fd, buf, 2)

            header = buf.getvalue()
            if len(header) == 0:
                break

            count, length = varint.decode(header)

            item = read(length)
            yield item, count
            buf.truncate(0)

        buf.close()


class NgramCounter(object):
    """Extract lexically sorted n-gram counts from generated text."""
    def __init__(self, tokenizer):
        """Init with a tokenizer.

        Args:
            tokenizer: a tokenizer object, must have a split() routine
                that returns tokens for a string.

        """
        self.tokenizer = tokenizer

    def _ngrams(self, grams, n):
        for i in xrange(0, len(grams) - n + 1):
            yield grams[i:i + n]

    def count(self, iterable, orders=(3,)):
        """Count the n-grams found in iterable.

        Args:
            iterable: an interable of tokenizable text
            orders: a tuple of n-gram orders to extract

        """
        ngrams = self._ngrams
        split = self.tokenizer.split
        join = "\t".join

        def items(lines):
            for line in lines:
                tokens = split(line)

                for n in orders:
                    for ngram in ngrams(tokens, n):
                        item = join(ngram)
                        yield item, 1

        counter = MergeCounter()
        return counter.count(items(iterable))
