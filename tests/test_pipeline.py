#!/usr/bin/env python3
"""One test per defect, written as the failing case. Standard library only.

Tests numbered `I-n` encode a defect found in `unused-assumptions` while
copying its code, and fixed at the copy rather than inherited. The rest encode
defects that shipped here.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import leanrun  # noqa: E402


class InheritedDefects(unittest.TestCase):
    """I-1 and I-2 in ENGINEERING.md."""

    def test_wait_for_memory_survives_entering_its_loop(self):
        """I-1. The original calls json.dumps and time.sleep and imports
        neither, so the *only* path that matters raises NameError. It never
        fired there because the loop was never entered. Force it."""
        polls = []
        original = leanrun.available_gb
        leanrun.available_gb = lambda: polls.append(1) or 0.5
        try:
            free = leanrun.wait_for_memory(minimum_gb=8.0, poll=0, limit=0)
        finally:
            leanrun.available_gb = original
        self.assertGreater(len(polls), 0, "the loop was not entered, so nothing was tested")
        self.assertEqual(free, 0.5)

    def test_wait_for_memory_returns_at_once_when_memory_is_free(self):
        original = leanrun.available_gb
        leanrun.available_gb = lambda: 99.0
        try:
            self.assertEqual(leanrun.wait_for_memory(minimum_gb=8.0, poll=0), 99.0)
        finally:
            leanrun.available_gb = original

    def test_plain_open_precedes_scoped(self):
        """I-2. `open scoped sigma` resolves as `ArithmeticFunction.sigma` and
        is an unknown namespace until `ArithmeticFunction` is open. The sibling
        emits scoped first and survives only via a duplicate raw emission."""
        prefix = leanrun.opened({"opens": "open ArithmeticFunction\nopen scoped sigma",
                                 "namespace": ""})
        lines = prefix.splitlines()
        plain = next(i for i, line in enumerate(lines) if line.startswith("open ArithmeticFunction"))
        scoped = next(i for i, line in enumerate(lines) if line.startswith("open scoped"))
        self.assertLess(plain, scoped)

    def test_the_masking_duplicate_is_not_copied(self):
        """The sibling emits every directive a second time, raw, ahead of both
        clauses. A bare `open` is a command: it persists for the rest of the
        file and lets one candidate elaborate on a neighbour's scope."""
        prefix = leanrun.opened({"opens": "open Function Set", "namespace": ""})
        for line in prefix.splitlines():
            self.assertTrue(line.endswith(" in"),
                            f"{line!r} is a bare open, and binds to the file")


class Scope(unittest.TestCase):

    def test_every_namespace_prefix_is_opened(self):
        """A declaration inside `A.B.C` may cite a name that resolves only
        under `A` or `A.B`. Opening the leaf alone loses the outer levels."""
        prefix = leanrun.opened({"opens": "", "namespace": "A.B.C"})
        names = prefix.removeprefix("open ").removesuffix(" in\n").split()
        self.assertEqual(names, ["A", "A.B", "A.B.C"])

    def test_no_directives_emits_nothing(self):
        self.assertEqual(leanrun.opened({"opens": "", "namespace": ""}), "")


class Header(unittest.TestCase):

    def test_mathlib_row_imports_only_the_umbrella(self):
        header = leanrun.header_for({"module": "Mathlib.Order.Basic"})
        self.assertNotIn("import Mathlib.Order.Basic", header)

    def test_other_corpus_imports_its_own_module(self):
        """TauCeti's root module is deliberately empty -- its lakefile builds
        by glob -- so importing the root brings nothing. Every name then fails
        to resolve and the corpus scores as pathologically over-constrained.
        That is on the record in the sibling's ENGINEERING.md."""
        header = leanrun.header_for({"module": "TauCeti.Analysis.Foo"})
        self.assertIn("import TauCeti.Analysis.Foo", header)

    def test_imports_precede_set_option(self):
        """An `import` after a command is a syntax error."""
        header = leanrun.header_for({"module": "TauCeti.Analysis.Foo"})
        self.assertLess(header.index("import TauCeti"), header.index("set_option"))


class Axioms(unittest.TestCase):
    """Success comes from `#print axioms`, never from the absence of an error."""

    def test_no_axioms_at_all_is_the_cleanest_result(self):
        """Lean spells this case without brackets. Matching only the bracketed
        form failed 40 rows in the sibling for being cleaner than required."""
        ok, why = leanrun.axioms_clean("'w1' does not depend on any axioms", "w1")
        self.assertTrue(ok, why)

    def test_fewer_than_three_axioms_is_still_clean(self):
        """Subset, never equality: demanding all three fails a proof using two."""
        ok, why = leanrun.axioms_clean("'w1' depends on axioms: [propext, Quot.sound]", "w1")
        self.assertTrue(ok, why)

    def test_sorry_is_not_clean(self):
        ok, _ = leanrun.axioms_clean(
            "'w1' depends on axioms: [propext, sorryAx]", "w1")
        self.assertFalse(ok)

    def test_a_record_naming_another_declaration_is_not_ours(self):
        ok, why = leanrun.axioms_clean("'other' does not depend on any axioms", "w1")
        self.assertFalse(ok)
        self.assertIn("w1", why)

    def test_a_missing_record_is_a_failure_not_a_pass(self):
        ok, _ = leanrun.axioms_clean("", "w1")
        self.assertFalse(ok)


class Errors(unittest.TestCase):

    def test_tagged_errors_are_caught(self):
        """Lean writes `error(lean.synthInstanceFailed):`, which does not
        contain the substring `error:`. A scan for the literal reads a file
        full of instance failures as clean."""
        found = leanrun.errors_in(
            "foo.lean:3:0: error(lean.synthInstanceFailed): failed to synthesize")
        self.assertEqual(len(found), 1)

    def test_plain_errors_are_caught(self):
        self.assertEqual(len(leanrun.errors_in("foo.lean:3:0: error: unknown identifier")), 1)

    def test_warnings_are_not_errors(self):
        """Linter noise about shadowed binders is inherited from the original
        declaration and must not fail a row."""
        self.assertEqual(leanrun.errors_in("foo.lean:3:0: warning: unused variable"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
