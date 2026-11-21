"""Replay the recorded pilot. Pass --live to make only missing model calls."""
import argparse
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from .cases import CONDITIONS, make_cases
from .scoring import mcnemar, score, wilson

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
PRICES = json.loads(Path(__file__).with_name('prices.json').read_text(), parse_float=Decimal)
RATES = PRICES['model_rates']
LIMIT = Decimal('2.50')
MAX_COMPLETION = 160
TITLE = 'Approver in the Footer'
QUESTION = 'Does repeating a name make AI think that person signed off?'
SETTINGS = {
    'gpt-5-nano-2025-08-07': {'reasoning_effort': 'minimal'},
    'gpt-4o-mini-2024-07-18': {'temperature': 0, 'seed': 2223},
}


def write_json(path, data):
    encoded = json.dumps(data, indent=2, ensure_ascii=True, default=float) + '\n'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(encoded)
    temporary.replace(path)


def request_body(model, case, condition):
    return {
        'model': model,
        'messages': case.messages(condition),
        'max_completion_tokens': MAX_COMPLETION,
        'response_format': {'type': 'json_object'},
        'service_tier': 'default',
        **SETTINGS[model],
    }


def digest(request):
    return sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


def tokens(response):
    usage = response['usage']
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)
    return {'input': usage['prompt_tokens'] - cached, 'cached_input': cached,
            'output': usage['completion_tokens']}


def cost(model, counts):
    return sum(RATES[model][kind] * value for kind, value in counts.items()) / 1_000_000


def call(request):
    body = json.dumps(request).encode()
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions', data=body,
        headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
                 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        error = json.load(exc).get('error', {})
        raise SystemExit(f'Model {request["model"]} returned HTTP {exc.code} ({error.get("code") or error.get("type")}).') from None
    except (TimeoutError, urllib.error.URLError):
        raise SystemExit('Provider request did not return a response. Check account usage before resuming.') from None


def read_cache():
    cache = {}
    for model in RATES:
        path = RESULTS / 'raw' / f'{model}.jsonl'
        for line in path.read_text().splitlines() if path.exists() else ():
            row = json.loads(line)
            key = (model, row['case'], row['condition'])
            if key in cache:
                raise SystemExit(f'Duplicate cache row for {key}')
            cache[key] = row
    return cache


def collect(cases, live):
    schedule = [(model, case, condition) for model in RATES for case in cases for condition in CONDITIONS]
    random.Random(2223).shuffle(schedule)
    cache = read_cache()
    active_keys = {(model, case.identifier, condition) for model, case, condition in schedule}
    if cache.keys() - active_keys:
        raise SystemExit('Cache contains rows outside the study design.')
    spent = sum(cost(key[0], tokens(row['response'])) for key, row in cache.items())
    for model, case, condition in schedule:
        key = (model, case.identifier, condition)
        request = request_body(model, case, condition)
        fingerprint = digest(request)
        if key in cache:
            if cache[key]['request_sha256'] != fingerprint:
                raise SystemExit(f'Cached request does not match the design for {key}')
            continue
        if not live:
            raise SystemExit(f'Missing recorded response for {key}')
        # An ASCII byte per input token plus framing is a conservative bound for this text.
        max_input = len(json.dumps(request).encode('ascii')) + 128
        maximum = cost(model, {'input': max_input, 'output': MAX_COMPLETION})
        if spent + maximum > LIMIT:
            raise SystemExit('Next call would exceed the study budget.')
        response = call(request)
        row = {'case': case.identifier, 'condition': condition, 'request_sha256': fingerprint,
               'response': response}
        path = RESULTS / 'raw' / f'{model}.jsonl'
        with path.open('a') as file:
            file.write(json.dumps(row) + '\n')
            file.flush()
            os.fsync(file.fileno())
        spent += cost(model, tokens(response))
        cache[key] = row
        print(f'{len(cache)}/{len(schedule)} recorded', flush=True)
    return cache


def response_text(response):
    choices = response.get('choices', [])
    if not choices or choices[0]['finish_reason'] != 'stop':
        return None
    return choices[0]['message'].get('content')


def odds_row(outcomes):
    n = len(outcomes)
    count = {name: outcomes.count(name) for name in ('correct', 'unsupported', 'missed', 'invalid')}
    return {'n': n, **count, 'unsupported_ci': wilson(count['unsupported'], n)}


def summarize(cases, cache):
    missing = [case for case in cases if case.expected is None]
    present = [case for case in cases if case.expected is not None]
    exemplar = missing[2]
    rows = {}
    examples = {}
    spend_models = {}
    contact_errors = dict.fromkeys(CONDITIONS, 0)
    for model in RATES:
        counts = dict.fromkeys(('input', 'cached_input', 'output'), 0)
        scored = {}
        responses = {}
        for case in cases:
            for condition in CONDITIONS:
                response = cache[(model, case.identifier, condition)]['response']
                text = response_text(response)
                responses[case.identifier, condition] = text
                outcome, name = score(text, case.expected)
                scored[case.identifier, condition] = outcome
                if case.expected is None and name == case.person:
                    contact_errors[condition] += 1
                for kind, value in tokens(response).items():
                    counts[kind] += value
        once_only, repeated_only = (sum(
            scored[case.identifier, active] == 'unsupported'
            and scored[case.identifier, other] == 'correct'
            for case in missing
        ) for active, other in (CONDITIONS, CONDITIONS[::-1]))
        valid_pairs = sum(all(scored[case.identifier, c] != 'invalid' for c in CONDITIONS) for case in missing)
        rows[model] = {
            **{c: odds_row([scored[case.identifier, c] for case in missing]) for c in CONDITIONS},
            'positive_controls': {c: odds_row([scored[case.identifier, c] for case in present]) for c in CONDITIONS},
            'valid_pairs': valid_pairs,
            'once_only': once_only,
            'repeated_only': repeated_only,
            'p': round(mcnemar(once_only, repeated_only), 8),
        }
        examples[model] = {c: {'output': responses[exemplar.identifier, c],
                              'score': scored[exemplar.identifier, c]} for c in CONDITIONS}
        spend_models[model] = {'tokens': counts, 'spend_usd': cost(model, counts)}
    date = datetime.fromtimestamp(min(row['response']['created'] for row in cache.values()),
                                  ZoneInfo('America/Detroit')).date().isoformat()
    totals = {c: sum(row[c]['unsupported'] for row in rows.values()) for c in CONDITIONS}
    pooled_n = len(missing) * len(rows)
    rate_sentence = (
        f'Models reported {totals["once"]} unsupported sign-offs with the name once and '
        f'{totals["repeated"]} with it repeated, out of {pooled_n} answers per condition.'
    )
    evidence = ('No clear effect from repeating the contact name. '
                if all(row['p'] >= .05 for row in rows.values()) else '')
    contact_sentence = (
        f'The models named the footer contact in {contact_errors["once"]}/{pooled_n} answers with the name once '
        f'and {contact_errors["repeated"]}/{pooled_n} with it repeated.'
    )
    summary = {
        'title': TITLE, 'question': QUESTION, 'date': date, 'cases': len(cases),
        'missing_cases': len(missing), 'positive_cases': len(present), 'calls': len(cache),
        'models': rows,
        'contact_errors': contact_errors,
        'finding': f'{evidence}{rate_sentence} {contact_sentence}',
        'example': {'code': exemplar.code,
                                    'contact': exemplar.person,
                                    'notes': list(exemplar.notes),
                                    'packets': {c: exemplar.packet(c) for c in CONDITIONS},
                                    'models': examples},
    }
    spend = {**PRICES, 'cap_usd': LIMIT, 'models': spend_models,
             'spend_usd': sum(x['spend_usd'] for x in spend_models.values())}
    return summary, spend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Make any missing OpenAI API calls.')
    arguments = parser.parse_args()
    if arguments.live:
        if not os.environ.get('OPENAI_API_KEY'):
            parser.error('--live needs OPENAI_API_KEY')
        import fcntl
        lock = RESULTS / 'raw' / '.live.lock'
        with lock.open('a') as file:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            cases = make_cases()
            cache = collect(cases, True)
    else:
        cases = make_cases()
        cache = collect(cases, False)
    summary, spend = summarize(cases, cache)
    write_json(RESULTS / 'summary.json', summary)
    write_json(RESULTS / 'spend.json', spend)
    print(f"Reproduced {summary['calls']} responses. Usage cost USD {spend['spend_usd']:.8f}.")


if __name__ == '__main__':
    main()
