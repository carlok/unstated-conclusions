#!/usr/bin/env python3
"""Tests for the store, written as the sibling's defects."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import store  # noqa: E402


def row(i: str) -> tuple:
    return (i, f"k{i}", "Mathlib", "Order", "Mathlib.Order.Basic", f"thm{i}",
            "", "", "[LE a]", "PartialOrder", "Preorder", "theorem x := y")


class Resumability(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.connection = store.connect(Path(self.dir.name) / "t.db")
        self.connection.executemany(
            "INSERT INTO candidate (id, key, corpus, area, module, theorem, namespace,"
            " opens, binder, stated_class, holds_over, source)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [row("a"), row("b")])
        self.connection.commit()

    def tearDown(self):
        self.dir.cleanup()

    def test_an_empty_store_is_not_a_finished_one(self):
        """The sibling reported an area as having zero findings by counting a
        stage that had not run. An empty store looks exactly like a completed
        one to anything that only asks 'are there undecided rows?'."""
        empty = store.connect(Path(self.dir.name) / "empty.db")
        self.assertFalse(store.complete(empty))

    def test_only_undecided_rows_are_handed_out(self):
        store.record(self.connection, "a", verdict="duplicate")
        self.assertEqual([r["id"] for r in store.pending(self.connection)], ["b"])

    def test_completeness_is_a_query_not_a_marker(self):
        self.assertFalse(store.complete(self.connection))
        store.record(self.connection, "a", verdict="duplicate")
        self.assertFalse(store.complete(self.connection))
        store.record(self.connection, "b", verdict="strengthens")
        self.assertTrue(store.complete(self.connection))

    def test_a_recorded_row_survives_reopening(self):
        """A kill must cost one compile, not an area."""
        store.record(self.connection, "a", verdict="strengthens", seconds=1.5)
        path = Path(self.dir.name) / "t.db"
        self.connection.close()
        again = store.connect(path)
        self.assertEqual(store.tally(again), {"strengthens": 1, "undecided": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ZeroOrHundred(unittest.TestCase):
    """A verdict category at 0% or 100% is a bug until proven otherwise."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import roots
        self.roots = roots

    def test_a_single_category_at_100_percent_is_flagged(self):
        """Defect 2: the first traversal returned 'no value' on every row, and
        a library with no proofs prints the same thing as a tool that cannot
        read them."""
        notes = self.roots.suspicious({"unreadable": 10}, 10)
        self.assertTrue(any("100%" in n for n in notes))

    def test_a_category_at_zero_is_flagged(self):
        notes = self.roots.suspicious({"matched": 0, "root_not_weakening": 10}, 10)
        self.assertTrue(any("0%" in n for n in notes))

    def test_a_healthy_spread_is_not_flagged(self):
        self.assertEqual(self.roots.suspicious({"matched": 3, "root_not_weakening": 7}, 10), [])

    def test_no_rows_at_all_is_flagged(self):
        self.assertEqual(self.roots.suspicious({}, 0), ["no rows at all"])


class NamePatternDuplicates(unittest.TestCase):
    """The sibling's prior-art stage filed a theorem's self-citations as
    genuine prior art, because it compared a leaf name against a dotted one.
    23 rows in one corpus and 63 in another landed in the wrong bucket."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import duplicates
        self.dup = duplicates

    def test_a_substitution_that_changes_nothing_is_not_a_sibling(self):
        """`Foo.bar` has no `_le` in it, so `_le -> _lt` yields `Foo.bar` back.
        Reporting that is the theorem citing itself."""
        found = self.dup.nominations("Foo.bar", [["_le", "_lt"]], {"Foo.bar"})
        self.assertEqual(found, [])

    def test_a_real_sibling_is_found(self):
        found = self.dup.nominations("Foo.add_le", [["_le", "_lt"]],
                                     {"Foo.add_le", "Foo.add_lt"})
        self.assertEqual(found, ["Foo.add_lt"])

    def test_a_guess_that_does_not_exist_is_not_reported(self):
        found = self.dup.nominations("Foo.add_le", [["_le", "_lt"]], {"Foo.add_le"})
        self.assertEqual(found, [])

    def test_dotted_names_are_handled_whole(self):
        """Never compare a leaf against a full name."""
        found = self.dup.nominations("A.B.c_le", [["_le", "_lt"]],
                                     {"A.B.c_lt", "other.c_lt"})
        self.assertEqual(found, ["A.B.c_lt"])

    def test_an_entry_with_no_convention_reports_nothing(self):
        """`Or.inl` has no naming convention worth guessing at, and inventing
        one would report siblings that are not there."""
        self.assertEqual(self.dup.nominations("Foo.bar_le", [], {"Foo.bar_lt"}), [])


class TableShape(unittest.TestCase):

    def test_every_entry_has_patterns_and_an_example(self):
        import json
        table = json.loads((Path(__file__).resolve().parent.parent
                            / "weakenings.json").read_text())
        for entry in table["entries"]:
            self.assertIn("sibling_patterns", entry, entry["root"])
            self.assertTrue(entry["example"].strip(), entry["root"])
            self.assertLess(entry["stronger_arg"], entry["explicit_arity"], entry["root"])

    def test_no_root_is_listed_twice(self):
        import json
        table = json.loads((Path(__file__).resolve().parent.parent
                            / "weakenings.json").read_text())
        roots = [e["root"] for e in table["entries"]]
        self.assertEqual(len(roots), len(set(roots)))


class GateSampling(unittest.TestCase):
    """The gate has to be able to come back positive.

    A uniform sample of a distribution dominated by one root is fifty rows
    about that root. That answers BRIEF.md's question only if the answer is the
    discouraging one, and a gate that can only fail is not a gate.
    """

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import gate
        self.gate = gate
        self.rows = ([{"decl": f"a{i}", "root": "le_of_lt"} for i in range(900)]
                     + [{"decl": f"b{i}", "root": "Exists.intro"} for i in range(80)]
                     + [{"decl": "c0", "root": "Filter.Eventually.of_forall"}]
                     + [{"decl": "d0", "root": "StrictMono.monotone"}])

    def test_every_root_that_fired_appears_at_least_once(self):
        sample = self.gate.stratified(self.rows, 50, seed=1)
        self.assertEqual({r["root"] for r in sample}, {r["root"] for r in self.rows})

    def test_a_root_with_one_occurrence_is_not_lost(self):
        """A root that fired once is the likeliest place for the narrow bucket,
        and proportional sampling would never show it."""
        sample = self.gate.stratified(self.rows, 50, seed=1)
        self.assertIn("c0", [r["decl"] for r in sample])

    def test_the_sample_is_the_size_asked_for(self):
        self.assertEqual(len(self.gate.stratified(self.rows, 50, seed=1)), 50)

    def test_a_pool_smaller_than_the_sample_is_returned_whole(self):
        small = self.rows[:3]
        self.assertEqual(len(self.gate.stratified(small, 50, seed=1)), 3)

    def test_the_same_seed_gives_the_same_fifty(self):
        """The gate is a document a person reads and argues with. It has to be
        the same document tomorrow."""
        first = [r["decl"] for r in self.gate.stratified(self.rows, 50, seed=7)]
        second = [r["decl"] for r in self.gate.stratified(self.rows, 50, seed=7)]
        self.assertEqual(first, second)

    def test_no_row_is_sampled_twice(self):
        sample = self.gate.stratified(self.rows, 50, seed=3)
        names = [r["decl"] for r in sample]
        self.assertEqual(len(names), len(set(names)))


class GeneratedLeanCommands(unittest.TestCase):
    """Defect 3: detailOf returns `MetaM Json` and was invoked as `MetaM Unit`.

    Fifty type errors, no rows, and -- because the renderer did not check --
    a gate document that said "no detail computed" fifty times and was still
    written. A reader could have drawn a conclusion from it, and the conclusion
    would have been about this tool rather than about Mathlib.
    """

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import sweep1
        self.sweep1 = sweep1
        self.row = {"id": "abc", "module": "Mathlib.Order.Basic", "namespace": "",
                    "source": "theorem wabc : True := trivial"}

    def test_detail_calls_are_wrapped_in_emitline(self):
        """A call whose result is discarded does not typecheck against Unit."""
        # EVERY generated #eval, not just the detail ones. The first version of
        # this test looked only at detailOf, and rootOf -- which returns
        # MetaM Json for the same reason -- went unwrapped and turned every row
        # into `context`.
        calls = [l for l in self.sweep1.file_for(self.row, "").splitlines()
                 if l.startswith("#eval")]
        self.assertTrue(calls, "no call was generated at all")
        for line in calls:
            self.assertIn("emitLine", line, line)

    def test_every_detail_index_gets_a_distinct_declaration_name(self):
        """Two addDecl calls under one name is an error the row would be
        blamed for."""
        calls = [l for l in self.sweep1.file_for(self.row, "").splitlines()
                 if l.startswith("#eval") and "detailOf" in l]
        names = [l.split("`strong")[1].split()[0] for l in calls]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), self.sweep1.MAX_INDEX)

    def test_the_sibling_module_is_passed_explicitly(self):
        """The weakened declaration is elaborated in a generated file and
        belongs to no module, so the sibling search would have nothing to
        scan and would report every row as unique."""
        body = self.sweep1.file_for(self.row, "")
        self.assertIn("`Mathlib.Order.Basic", body)


class RootShiftJoin(unittest.TestCase):
    """Defect 10: a name that never matches drops a row from a measurement,
    and a dropped row and a row with nothing to say leave the same absence."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import rootshift
        self.rs = rootshift

    def test_a_root_escape_resolves_to_the_real_name(self):
        """`Prod._root_.WCovBy.fst` is the namespace it was written in followed
        by the escape leaving that namespace. Lean calls it `WCovBy.fst`."""
        self.assertEqual(self.rs.real_name("Prod._root_.WCovBy.fst"), "WCovBy.fst")

    def test_an_ordinary_name_is_untouched(self):
        self.assertEqual(self.rs.real_name("Finset.sum_le_sum"), "Finset.sum_le_sum")

    def test_a_name_that_merely_contains_root_is_untouched(self):
        self.assertEqual(self.rs.real_name("Polynomial.roots_nodup"),
                         "Polynomial.roots_nodup")


class RootShiftAuxiliaries(unittest.TestCase):
    """Defect 11: a `match` auxiliary is named after its parent, and the sweep
    renames every parent to `w<id>`. Compared raw, the same auxiliary reads as
    a different root -- and inflates the measurement in the direction that
    makes the expensive Part 2 design look necessary."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import rootshift
        self.rs = rootshift

    def test_the_same_match_auxiliary_compares_equal(self):
        before = self.rs.normalise_root(
            "_private.Mathlib.Algebra.Order.Archimedean.Basic.0.exists_rat_lt.match_1_1",
            "exists_rat_lt")
        after = self.rs.normalise_root("w70947a3b59313356.match_1_1", "exists_rat_lt")
        self.assertEqual(before, after)

    def test_a_genuine_change_of_root_is_not_normalised_away(self):
        """The thing being measured must survive the fix that makes it
        measurable."""
        before = self.rs.normalise_root("Polynomial.not_isField", "x")
        after = self.rs.normalise_root(
            "Mathlib.Tactic.Nontriviality.subsingleton_or_nontrivial_elim", "x")
        self.assertNotEqual(before, after)

    def test_an_ordinary_root_is_untouched(self):
        self.assertEqual(self.rs.normalise_root("le_of_lt", "x"), "le_of_lt")

    def test_proof_auxiliaries_normalise_too(self):
        self.assertEqual(self.rs.normalise_root("Foo.bar._proof_3", "Foo.bar"),
                         self.rs.normalise_root("wabc._proof_3", "Foo.bar"))


class SorryIsNeverAFinding(unittest.TestCase):
    """Defect 12. Lean inserts `sorryAx` when a tactic fails, so a declaration
    whose proof did not work is still added and `addDecl` on a subterm of it
    still succeeds. Accepting a compile shot on positive evidence rather than
    on silence -- this project's own relaxation -- is what opened the door."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import sweep1, roots
        self.sweep1, self.table = sweep1, roots.load_table()

    def test_a_sorried_row_is_not_a_finding_even_with_a_table_root(self):
        answers = [{"ok": True, "root": "le_of_lt", "layers": 0, "root_args": 5,
                    "has_sorry": True},
                   {"ok": True, "root": "le_of_lt", "explicit_index": 0,
                    "peel_preserved_type": True, "verify": "added",
                    "stronger": "a < b", "stated": "a <= b", "has_sorry": True}]
        out = self.sweep1.decide(answers, self.table)
        self.assertEqual(out["verdict"], "context")
        self.assertIn("sorryAx", out["detail"])

    def test_a_clean_row_with_the_same_shape_is_a_finding(self):
        """The guard must not swallow the rows it is guarding."""
        answers = [{"ok": True, "root": "le_of_lt", "layers": 0, "root_args": 5,
                    "has_sorry": False},
                   {"ok": True, "root": "le_of_lt", "explicit_index": 0,
                    "peel_preserved_type": True, "verify": "added",
                    "stronger": "a < b", "stated": "a <= b", "has_sorry": False}]
        self.assertEqual(self.sweep1.decide(answers, self.table)["verdict"], "strengthens")


class WitnessIsNotAFailure(unittest.TestCase):
    """Defect 13. Defect 7 taught the kernel to accept a non-Prop
    strengthening as a `def`, and reported it as `added as a definition`.
    decide() still tested `verify != "added"`, so the row that fix existed to
    rescue was recorded as `context` -- the tool's own failure."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import sweep1, roots
        self.sweep1, self.table = sweep1, roots.load_table()

    def _answers(self, verify, is_prop):
        return [{"ok": True, "root": "Nonempty.intro", "layers": 0, "root_args": 2,
                 "has_sorry": False},
                {"ok": True, "root": "Nonempty.intro", "explicit_index": 0,
                 "peel_preserved_type": True, "verify": verify, "is_prop": is_prop,
                 "stronger": "A", "stated": "Nonempty A", "has_sorry": False}]

    def test_a_definition_is_a_witness_not_a_context_failure(self):
        out = self.sweep1.decide(self._answers("added as a definition", False), self.table)
        self.assertEqual(out["verdict"], "witness")

    def test_a_real_kernel_failure_is_still_context(self):
        out = self.sweep1.decide(self._answers("addDecl failed: nope", True), self.table)
        self.assertEqual(out["verdict"], "context")

    def test_an_ordinary_proposition_is_still_strengthens(self):
        out = self.sweep1.decide(self._answers("added", True), self.table)
        self.assertEqual(out["verdict"], "strengthens")


class TrackDSourceProvenance(unittest.TestCase):
    """Defect 16, and the data finding under it.

    The sibling's export ships ONE source per row, and for a binder that both
    held somewhere and broke somewhere it ships the source that HELD. So for
    exactly the rows Track D needs, the failing compile has no source attached.
    Rebuilding one is possible and is not free: the sibling rebuilt six sources
    by rewriting a binder and all six stopped compiling.
    """

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import trackd
        self.trackd = trackd

    def row(self, source, binder="[IsDomain R]", fails_at="Nontrivial",
            holds_over="NoZeroDivisors"):
        return {"source": source, "binder": binder, "fails_at": fails_at,
                "holds_over": holds_over}

    def test_a_source_already_at_fails_at_is_used_as_shipped(self):
        src, prov, _ = self.trackd.source_at(
            self.row("theorem w {R} [Nontrivial R] : True := trivial"))
        self.assertEqual(prov, "as_shipped")
        self.assertIn("[Nontrivial R]", src)

    def test_a_source_at_holds_over_is_reconstructed_and_marked(self):
        src, prov, _ = self.trackd.source_at(
            self.row("theorem w {R} [NoZeroDivisors R] : True := trivial"))
        self.assertEqual(prov, "reconstructed")
        self.assertIn("[Nontrivial R]", src)
        self.assertNotIn("[NoZeroDivisors R]", src)

    def test_the_class_must_apply_to_the_binder_s_own_variable(self):
        """`Ne.isUnit_C` passed a bare class-name check because its source
        carried `[CommRing R]` while the binder under test was `[Field k]`. It
        was recorded as compiling at a class it was never rebuilt at."""
        src, prov, why = self.trackd.source_at(self.row(
            "theorem w {k R} [DivisionRing k] [CommRing R] : True := trivial",
            binder="[Field k]", fails_at="CommRing", holds_over="DivisionRing"))
        self.assertEqual(prov, "reconstructed")
        self.assertIn("[CommRing k]", src)
        self.assertIn("[CommRing R]", src)  # the other variable is untouched

    def test_a_source_carrying_neither_class_is_a_mismatch(self):
        src, prov, _ = self.trackd.source_at(
            self.row("theorem w {R} [Ring R] : True := trivial"))
        self.assertIsNone(src)
        self.assertEqual(prov, "mismatch")

    def test_a_binder_with_no_variable_is_a_mismatch(self):
        src, prov, _ = self.trackd.source_at(self.row("x", binder="[Foo]"))
        self.assertIsNone(src)


class ShippedArtefactsCarryNoTempPaths(unittest.TestCase):
    """Defect 23. Lean prints the filename it is handed, and we hand it a temp
    file, so `/var/folders/.../tmpXXXX.lean` reached the `detail` column of a
    shipped artefact.

    This is the sibling's ENGINEERING #4 exactly: a temp path reached a
    published document there, and the source had been grepped for `/Users`,
    `/private` and `/tmp`. macOS puts temp files under `/var/folders`. We had
    the story written down in `docs/from-the-brother.md` and shipped the defect
    anyway.
    """

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        import export_rows
        self.redact = export_rows.redact

    def test_var_folders_is_redacted(self):
        self.assertEqual(
            self.redact("lean: /var/folders/ck/62d1g/T/tmpabc.lean:5:0: error"),
            "lean: <tempfile>:5:0: error")

    def test_private_var_folders_is_redacted(self):
        self.assertNotIn("/var/folders",
                         self.redact("at /private/var/folders/x/T/tmpq.lean"))

    def test_tmp_is_redacted(self):
        self.assertNotIn("/tmp/", self.redact("/tmp/tmpfoo.lean:1:1: error"))

    def test_ordinary_text_is_untouched(self):
        text = "the proof rests on sorryAx"
        self.assertEqual(self.redact(text), text)

    def test_non_strings_pass_through(self):
        self.assertEqual(self.redact(7), 7)
        self.assertIsNone(self.redact(None))

    def test_no_shipped_file_carries_a_temp_path(self):
        """The check that would have caught it: read the artefact, not the
        code that writes it."""
        data = Path(__file__).resolve().parent.parent / "data"
        for path in sorted(data.glob("*.json")) + sorted(data.glob("*.jsonl")):
            text = path.read_text()
            for needle in ("/var/folders", "/private/var", "/tmp/"):
                self.assertNotIn(needle, text, f"{path.name} carries {needle}")
