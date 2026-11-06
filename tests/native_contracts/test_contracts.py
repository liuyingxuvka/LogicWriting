"""Original independent rules, original bad observations, and actual code.

The bad observations exercise the independent predicates, not production
mutations. Actual correspondence is asserted separately against real scripts.
"""
import pytest

from .contract_cases import TOPICS, actual, cases, contract

RULES = [(topic, rule) for topic in TOPICS for rule in contract(topic).RULES]
BAD = [(topic, name) for topic in TOPICS for name in contract(topic).BAD_EXPECTATIONS]


@pytest.mark.parametrize("topic,rule", RULES, ids=[f"{t}:{r}" for t, r in RULES])
def test_independent_rule(topic, rule):
    module = contract(topic)
    for state, events in cases(topic):
        assert module.RULES[rule](state)
        for event in events:
            _, state = module.CALCULATE(event, state)
            assert module.RULES[rule](state), (topic, rule, event, state)


@pytest.mark.parametrize("topic,name", BAD, ids=[f"{t}:{n}" for t, n in BAD])
def test_rejects_original_bad_observation(topic, name):
    module = contract(topic)
    calculate = module.BAD_EXPECTATIONS[name]
    for state, events in cases(topic):
        for event in events:
            _, state = calculate(event, state)
            if any(not predicate(state) for predicate in module.RULES.values()):
                return
    pytest.fail(f"the retained predicates did not reject {topic}:{name}")


@pytest.mark.parametrize("topic", TOPICS)
def test_actual_functional_contract(topic):
    module = contract(topic)
    # Each reset starts a new real temporary artifact/request. A fixture is
    # closed before the next reset, including on assertion or production error.
    for initial, events in cases(topic, functional=True):
        with actual(topic) as native:
            native.reset(initial)
            state = initial
            for event in events:
                expected = module.CALCULATE(event, state)
                observed = native.observe(event)
                assert observed == expected, (topic, event, observed, expected)
                state = observed[1]
                assert all(predicate(state) for predicate in module.RULES.values())
