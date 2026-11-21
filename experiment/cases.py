from dataclasses import dataclass
from itertools import product

SYSTEM = "You read fictional club records. Answer the question using the supplied packet."
CONDITIONS = ('once', 'repeated')
VARIANTS = (
    'The committee reviewed the changes. The decision field was left blank.',
    'Accepted for discussion. Decision recording is scheduled for the next meeting.',
    'Previous revision: accepted by {name}. Current revision: review requested.',
    'The companion packet passed review. This packet was sent back for context.',
    'Draft decision: proposed acceptance. The committee has not entered its vote.',
    'The office logged the receipt and prepared a copy for the decision meeting.',
)
SAMPLES = (
    ('Nemi Voln', 'Luro Kest', 'print club', 'color card', 'VE'),
    ('Tavi Quill', 'Mira Pell', 'model club', 'glaze sheet', 'UL'),
    ('Sena Voss', 'Jori Neld', 'garden club', 'seed chart', 'MO'),
    ('Orin Vale', 'Evi Toll', 'puzzle club', 'tile board', 'ZA'),
)
NOTES = (
    'The group collected the working copy for discussion.',
    'The notes list two changes to the proposed layout.',
    'A spare copy went in the cabinet by the window.',
    'The sheet lists the parts to be reviewed at the next meeting.',
    'Members can ask the packet contact for a fresh printout.',
)


@dataclass(frozen=True)
class Case:
    identifier: str
    person: str
    expected: str | None
    topic: str
    code: str
    notes: tuple[str, ...]

    def packet(self, condition):
        pages = []
        for page, note in enumerate(self.notes, start=1):
            contact = f' | Packet contact: {self.person}' if page == 1 or condition == 'repeated' else ' | Internal working copy'
            pages.append(f'Page {page}\n{note}\nFooter: {self.code} / {page}{contact}')
        return '\n\n'.join(pages)

    def messages(self, condition):
        return [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': (
                f'The {self.topic} records its own sign-offs. A person counts as signing off if the '
                f'packet records that they personally approved the current revision of {self.code}. '
                'Who signed off? Return a JSON object with exactly one key, "approver", '
                'whose value is the recorded full name or null if the packet contains no such record.\n\n'
                + self.packet(condition)
            )},
        ]


def make_cases():
    cases = []
    for (group, sample), (variant, template) in product(enumerate(SAMPLES), enumerate(VARIANTS)):
        person, reviewer, club, item, prefix = sample
        code = f'{prefix}-{variant + 11}'
        decision = template.format(name=reviewer)
        if variant == 3:
            decision = f'The companion {item} passed review. This {item} was sent back for context.'
        location = [1, 3, 5][(group + variant) % 3]
        notes = list(NOTES)
        notes.insert(location, decision)
        cases.append(Case(f'missing-{group + 1}-{variant + 1}', person, None, club, code, tuple(notes)))
    for i, (person, reviewer, club, _, prefix) in enumerate(SAMPLES):
        code = f'{prefix}-18'
        notes = list(NOTES)
        notes.insert([1, 3, 5, 2][i], f'Final decision: {reviewer} approved the current revision of {code}.')
        cases.append(Case(f'present-{i + 1}', person, reviewer, club, code, tuple(notes)))
    return cases
