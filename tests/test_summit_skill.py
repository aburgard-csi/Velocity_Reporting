"""The Executive Summit one-pager skill keeps CLAUDE.md's rule: hand-built, per named attendee, metrics are Aaron's call."""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_summit_skill_names_real_files_and_keeps_its_guards():
    text = open(os.path.join(REPO, ".claude", "skills", "summit-one-pager", "SKILL.md"), encoding="utf-8").read()
    head = re.match(r"---\nname: ([\w-]+)\ndescription: (.+)\n---\n", text)
    assert head and head.group(1) == "summit-one-pager"
    for path in re.findall(r"(?:build/ars_pipeline|scripts)/\w+\.py", text):
        assert os.path.isfile(os.path.join(REPO, path)), path
    assert os.path.isfile(os.path.join(REPO, "templates", "ars_template.pptx"))
    for phrase in ("which attendees", "never choose the metrics", "build_month.py", "RPE_PERIOD", "responder_activity.py",
                   "Do not", "Right story for"):
        assert phrase.lower() in text.lower(), phrase
