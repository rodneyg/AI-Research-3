import json
from math import comb, sqrt


def score(content, expected):
    try:
        result = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return ('invalid', None)
    if not isinstance(result, dict) or set(result) != {'approver'}:
        return ('invalid', None)
    approver = result['approver']
    if approver is not None:
        if not isinstance(approver, str) or not approver.strip():
            return ('invalid', None)
        approver = ' '.join(approver.split())
    if approver == expected:
        return ('correct', approver)
    return ('unsupported' if approver else 'missed', approver)


def wilson(successes, total):
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half_width = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, center - half_width), 6), round(min(1.0, center + half_width), 6)]


def mcnemar(a_only, b_only):
    """Two-sided exact McNemar p value conditioned on discordant pairs."""
    discordant = a_only + b_only
    tail = sum(comb(discordant, k) for k in range(min(a_only, b_only) + 1))
    return min(1.0, 2 * tail / 2**discordant)
