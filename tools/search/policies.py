"""Interpret persisted search policies strictly, including historical runs."""


def search_options(result):
    policies = result.get('policies', {})
    options = {}
    for field, argument, choices in (
        ('self_match', 'exclude_self', {
            'exclude all identical input-byte SHA-256': True,
            'include self matches': False}),
        ('duplicates', 'deduplicate', {
            'one representative per SHA-256; lowest distance then lexical tie': True,
            'all eligible files ranked independently, including identical SHA-256': False}),
    ):
        value = policies.get(field)
        if value not in choices:
            raise ValueError(f'Unknown saved {field} policy: {value!r}')
        options[argument] = choices[value]
    return options
