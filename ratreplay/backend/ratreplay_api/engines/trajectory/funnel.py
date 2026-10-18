"""
The funnel: which sessions of the transformed folder are in the dataset under the rules, why the others are not, and the epochs the rules select.
"""

from .cuts import selected

# What a session that is out says, in the order the rules are checked. The epoch reason names the rules' kinds and condition.
OUT_PROTOCOL = "protocol {found}, not {wanted}"
OUT_GROUP = "group {group} is excluded"
OUT_ANNOTATION = "excluded by annotation"
OUT_EPOCHS = "no {kinds} epoch under condition {condition}"
OUT_FRAMES = "no frames"


def session_reason(session, excluded, rules):
    """
    Why the session is out by its own row and the annotations, none when it stays.
    """
    if session["protocol"] != rules["protocol"]:
        return OUT_PROTOCOL.format(found=session["protocol"], wanted=rules["protocol"])
    if session["group"] in rules["excluded_groups"]:
        return OUT_GROUP.format(group=session["group"])
    if session["session_id"] in excluded:
        return OUT_ANNOTATION
    return None


def funnel(tables, rules):
    """
    Per session id whether it is in the dataset and the reason when not, with the epochs the rules select among those of a session that passed its own checks.
    """
    excluded = {row["session_id"] for row in tables["annotations"] if row.get("exclude")}
    found = {}
    for session in tables["sessions"]:
        sid = session["session_id"]
        reason = session_reason(session, excluded, rules)
        epochs = [] if reason else selected([e for e in tables["epochs"] if e["session_id"] == sid], rules)
        if reason is None and not epochs:
            reason = OUT_EPOCHS.format(kinds=" or ".join(rules["epochs"]), condition=rules["condition"])
        if reason is None and sid not in tables["frames"]:
            reason = OUT_FRAMES
        found[sid] = {"in_dataset": reason is None, "reason": reason, "epochs": epochs}
    return found
