from django.db import migrations


COLLECTIONS = [
    ("vulnerabilities", "VULN", "Vulnerabilities in Electronic Voting and Ballot-Counting Systems", "Primary-source records concerning reported technical vulnerabilities in election technology. A vulnerability does not, by itself, establish exploitation or an altered vote.", 1),
    ("china-voter-data", "CHINA", "China’s Acquisition and Exploitation of American Voter Data", "Records concerning reported acquisition, access, or use of American voter data, with allegations and assessments labeled by source and review status.", 2),
    ("michigan-registration", "MICH", "Michigan Voter-Registration Investigation", "Investigative records and correspondence concerning Michigan voter-registration activity. Registration applications, accepted registrations, ballots, charges, and convictions remain distinct evidence categories.", 3),
    ("noncitizen-rolls", "NONCIT", "Noncitizens on State Voter Rolls", "Records concerning possible or confirmed noncitizen matches on voter rolls. Database matches are not presented as registrations or votes without source evidence.", 4),
]


def seed(apps, schema_editor):
    Collection = apps.get_model("archive", "Collection")
    for slug, code, title, description, order in COLLECTIONS:
        Collection.objects.update_or_create(slug=slug, defaults={"code": code, "title": title, "description": description, "display_order": order})


def unseed(apps, schema_editor):
    apps.get_model("archive", "Collection").objects.filter(slug__in=[row[0] for row in COLLECTIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("archive", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
