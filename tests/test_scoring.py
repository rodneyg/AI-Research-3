import unittest

from experiment.cases import make_cases
from experiment.scoring import mcnemar, score, wilson


class ScoringTests(unittest.TestCase):
    def test_recorded_absence(self):
        self.assertEqual(score('{"approver":null}', None), ('correct', None))
        self.assertEqual(score('{"approver":"Nemi Voln"}', None), ('unsupported', 'Nemi Voln'))

    def test_positive_control(self):
        self.assertEqual(score('{"approver":" Luro  Kest "}', 'Luro Kest'), ('correct', 'Luro Kest'))
        self.assertEqual(score('{"approver":null}', 'Luro Kest'), ('missed', None))
        self.assertEqual(score('{"approver":"Nemi Voln"}', 'Luro Kest'), ('unsupported', 'Nemi Voln'))

    def test_invalid_answers_are_separate(self):
        for answer in (None, 'null', '[]', '{}', '{"approver":1}', '{"approver":""}', 'invalid'):
            with self.subTest(answer=answer):
                self.assertEqual(score(answer, None), ('invalid', None))

    def test_intervals_and_paired_test(self):
        self.assertEqual(wilson(0, 24), [0.0, 0.137976])
        self.assertEqual(wilson(4, 24), [0.066787, 0.358531])
        self.assertEqual(mcnemar(0, 0), 1)
        self.assertEqual(mcnemar(0, 5), 0.0625)
        self.assertEqual(mcnemar(5, 0), 0.0625)

    def test_pair_design(self):
        cases = make_cases()
        self.assertEqual(len(cases), 28)
        self.assertEqual(len({case.identifier for case in cases}), len(cases))
        self.assertEqual(sum(case.expected is None for case in cases), 24)
        for case in cases:
            once, repeated = (case.packet(c).splitlines() for c in ('once', 'repeated'))
            self.assertEqual(sum(a != b for a, b in zip(once, repeated, strict=True)), 5)
            self.assertEqual(sum('Packet contact:' in line for line in once), 1)
            self.assertEqual(sum('Packet contact:' in line for line in repeated), 6)
