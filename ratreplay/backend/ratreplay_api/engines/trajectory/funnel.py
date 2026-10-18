"""
The funnel: which sessions of the transformed folder the tool can work with under the rules, why the others are not, and the epochs the rules select. It never excludes by a tag, the person excludes.
"""

from .cuts import selected

# What a session the tool cannot work with says, in the order the rules are checked. The epoch reason names the rules' kinds and condition.
OUT_EPOCHS = "no {kinds} epoch under condition {condition}"
OUT_FRAMES = "no frames"


def funnel(tables, rules):
    """
    Per session id whether it is in the dataset, the reason when not (no epoch of the rules' kinds and condition, or no frames), the epochs the rules select and whether the annotations table marks it excluded, a note and not a rule.
    """
    annotated = {row["session_id"] for row in tables["annotations"] if row.get("exclude")}
    found = {}
    for session in tables["sessions"]:
        sid = session["session_id"]
        epochs = selected([e for e in tables["epochs"] if e["session_id"] == sid], rules)
        reason = None
        if not epochs:
            reason = OUT_EPOCHS.format(kinds=" or ".join(rules["epochs"]), condition=rules["condition"])
        elif sid not in tables["frames"]:
            reason = OUT_FRAMES
        found[sid] = {"in_dataset": reason is None, "reason": reason, "epochs": epochs, "annotated_exclude": sid in annotated}
    return found
