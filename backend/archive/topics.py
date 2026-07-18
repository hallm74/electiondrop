TOPICS = (
    {
        "slug": "michigan-registration",
        "label": "Michigan registration investigation",
        "aliases": ("michigan", "fake voter", "fraudulent registration", "gbi strategies"),
        "collection_slugs": ("michigan-registration",),
    },
    {
        "slug": "china-prc",
        "label": "China / PRC",
        "aliases": ("china", "chinese", "prc", "beijing"),
        "collection_slugs": ("china-voter-data",),
    },
    {
        "slug": "burisma-ukraine",
        "label": "Burisma & Ukraine",
        "aliases": ("burisma", "ukraine", "ukrainian"),
        "collection_slugs": (),
    },
    {
        "slug": "voter-registration",
        "label": "Voter registration",
        "aliases": ("voter registration", "registration application"),
        "collection_slugs": (),
    },
    {
        "slug": "fraudulent-registrations",
        "label": "Fake or fraudulent registrations",
        "aliases": ("fake registration", "fake voter", "fraudulent registration", "falsified registration", "forged registration"),
        "collection_slugs": (),
    },
    {
        "slug": "voter-data",
        "label": "Voter data",
        "aliases": ("voter data", "voter records", "voter information", "voterregistration information"),
        "collection_slugs": (),
    },
    {
        "slug": "data-compromise",
        "label": "Data compromise",
        "aliases": ("compromised", "data breach", "stolen data"),
        "collection_slugs": (),
    },
    {
        "slug": "election-infrastructure",
        "label": "Election infrastructure",
        "aliases": ("election infrastructure",),
        "collection_slugs": (),
    },
    {
        "slug": "election-vulnerabilities",
        "label": "Election vulnerabilities",
        "aliases": ("vulnerability", "vulnerabilities"),
        "collection_slugs": ("vulnerabilities",),
    },
    {
        "slug": "voting-machines",
        "label": "Voting machines & systems",
        "aliases": ("voting machine", "voting system", "election system"),
        "collection_slugs": (),
    },
    {
        "slug": "election-security",
        "label": "Election security",
        "aliases": ("election security", "cybersecurity"),
        "collection_slugs": (),
    },
    {
        "slug": "ballots",
        "label": "Ballots",
        "aliases": ("ballot", "ballots"),
        "collection_slugs": (),
    },
    {
        "slug": "fbi",
        "label": "FBI",
        "aliases": ("fbi",),
        "collection_slugs": (),
    },
    {
        "slug": "cisa",
        "label": "CISA",
        "aliases": ("cisa",),
        "collection_slugs": (),
    },
    {
        "slug": "russia",
        "label": "Russia",
        "aliases": ("russia", "russian"),
        "collection_slugs": (),
    },
    {
        "slug": "iran",
        "label": "Iran",
        "aliases": ("iran", "iranian"),
        "collection_slugs": (),
    },
    {
        "slug": "noncitizen-voter-rolls",
        "label": "Noncitizen voter rolls",
        "aliases": ("noncitizen", "non-citizen", "alien voter", "alien registration"),
        "collection_slugs": ("noncitizen-rolls",),
    },
    {
        "slug": "foreign-election-threats",
        "label": "Foreign election threats",
        "aliases": ("foreign threat", "foreign interference", "foreign influence"),
        "collection_slugs": (),
    },
    {
        "slug": "venezuela",
        "label": "Venezuela",
        "aliases": ("venezuela", "venezuelan"),
        "collection_slugs": (),
    },
)


def get_topic(slug):
    return next((topic for topic in TOPICS if topic["slug"] == slug), None)
