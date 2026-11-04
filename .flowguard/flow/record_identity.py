"""A changed record cannot reuse its old exact-object fingerprint.

This finite native boundary exercises the real shared identity validator. Reader
isolation, schema, routing, provider and artifact-chain contracts remain direct
functional tests; this is not a model of every writing workflow.
"""
from flowguard.flow import Model, need
from flowguard.flow.adapter import fields

m = Model("exact record identity", covers=["skills/logic-writing/scripts/_common.py"])
m.field("version", (0, 1), 0)
m.field("accepted", (False, True), False)


@m.action()
def edit(s):
    s["version"], s["accepted"] = 1, False


@m.action()
def restore(s):
    s["version"], s["accepted"] = 0, False


@m.action()
def check(s):
    need(s["version"] == 0, "the current object must match its frozen fingerprint")
    s["accepted"] = True


m.always("changed_record_is_refused", lambda s: s["version"] == 0 or not s["accepted"])
m.after("editing changes the checked record", "edit", lambda before, after: after["version"] == 1)
m.after("restoring invalidates an earlier observation", "restore", lambda before, after: not after["accepted"])
m.reach("a matching object can be checked", lambda s: s["accepted"])
m.bind_adapter({"system": "tests.flow_migration.native_identity:RecordWorld",
                "classes": ["tests.flow_migration.native_identity:RecordWorld"],
                "refusal": ["builtins:ValueError"]},
               state=lambda snapshot: fields(snapshot, names=("version", "accepted")),
               operations={"edit": "edit", "restore": "restore", "check": "check"})
MODEL = m
