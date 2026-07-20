"""Braudit 3-Question Assessment.

Copy and scoring implemented from "Braudit - 3 Question Assessment Copy.md"
(TMH Content Engine) — that doc is the source of truth for wording; edit
there, mirror here.

Design principle carried over verbatim: nothing is rigged. Every "get help"
conclusion is earned by a risk the visitor just told us about; genuinely
simple cases are told so (Band C), which is what makes the rest credible.

The one dynamic element: Q2's "similar names found" flag is fed from the
report's own search results, so it reads as personal fact, not hypothesis —
the doc calls it the single most persuasive line on the page.
"""
from __future__ import annotations

LINKS = {
    'enquiry': 'https://www.thetrademarkhelpline.com/make-an-enquiry/',
    'talk': 'https://link.cerebrumai.io/widget/booking/ZArxD6BnggpV7bsSF0ks',
    'audit': 'https://www.thetrademarkhelpline.com/request-brand-audit/',
}

Q1 = {
    'question': 'How much of your business would you have to rebuild if you '
                'had to change your name?',
    'options': [
        ("Very little — we're pre-launch or still testing the idea", 1,
         "Good timing. The cheapest moment to protect a name is before you "
         "have built anything on it. Nothing to unpick, no customers to "
         "re-educate, no printed material to bin."),
        ("Some — we've got a website and socials but not much traction yet", 2,
         "You are at the point where a name change starts to sting. New site, "
         "new handles, new artwork, and the search rankings you have started "
         "to build go back to zero."),
        ("A lot — customers find us and recommend us by name", 4,
         "Once customers recommend you by name, the name is doing your "
         "marketing for you. That is the point at which it stops being a "
         "label and starts being an asset worth protecting."),
        ("Almost everything — the name is the business", 5,
         "If the name is the business, it is probably your most valuable "
         "asset, and the one most exposed. Reputation, repeat customers, "
         "listings and contracts all sit on top of it."),
    ],
}

Q2 = {
    'question': 'Which of these apply to your situation?',
    'options': [
        ("The search found businesses with similar names, or names in a "
         "similar sector", 3,
         "This is the most common reason applications run into trouble. An "
         "existing similar mark can lead to an objection or an opposition "
         "from the other owner, and official fees are not refunded if your "
         "application fails."),
        ("We sell more than one type of product or service", 2,
         "Each category of goods or services is a separate class. Choose too "
         "few and you protect less than you think. Choose too many and you "
         "pay for cover you do not need. Getting the specification right is "
         "most of the work."),
        ("We sell, or plan to sell, outside the UK", 2,
         "Trademark rights are territorial. A UK registration stops at the UK "
         "border, so anywhere else you trade is open unless you register "
         "there too. This catches out a lot of businesses selling through "
         "online marketplaces."),
        ("Our name partly describes what we do", 2,
         "Names that describe the product, the place or the industry can be "
         "refused for lacking distinctiveness. It is one of the most common "
         "refusal grounds and it is difficult to spot from the outside."),
        ("We use both a name and a logo, and aren't sure which to protect", 2,
         "A word mark protects the name in any font or colour. A logo mark "
         "protects that particular design. Protect the wrong one and a "
         "competitor can keep using the part that actually matters to your "
         "customers."),
    ],
    'none_option': ("None of these: it's a made-up word, one product, UK only",
                    "On the face of it yours looks like one of the more "
                    "straightforward cases. Worth running a free search "
                    "before you commit either way, but you may well not need "
                    "much help with this."),
}

Q3 = {
    'question': 'If your application were refused, or someone opposed it, '
                'what would you want to happen?',
    'options': [
        ("I'd want to have known before I filed and spent the money", 4,
         "That is exactly what an audit is for. Research first, so you either "
         "file knowing where you stand, or you find out early that this "
         "particular name is not worth spending on."),
        ("I'd want someone to handle the objection for me", 4,
         "Worth knowing the scale before it happens. Defending an opposition "
         "typically runs to around ten hours of professional time, and rates "
         "in this market sit between £99 and £499 an hour."),
        ("I'd have a go at sorting it myself", 1,
         "Fair enough, and plenty of people do. The thing worth knowing is "
         "where the cost lands if it goes wrong, because the official fee is "
         "not returned and the time cost of a contested application adds up "
         "quickly."),
        ("I hadn't realised either of those could happen", 3,
         "Most people have not. Applications can be refused, official fees "
         "are not refunded, and once your application is published third "
         "parties get a window in which to oppose it."),
    ],
}


def score(q1_idx: int, q2_flags: list[int], q2_none: bool,
          q3_idx: int) -> dict:
    """Band A/B/C per the doc, with the DIY-preference modifier."""
    q1 = Q1['options'][q1_idx][1] if q1_idx is not None else 0
    q2 = 0 if q2_none else sum(Q2['options'][i][1] for i in q2_flags)
    q3 = Q3['options'][q3_idx][1] if q3_idx is not None else 0
    total = q1 + q2 + q3
    band = 'A' if total >= 13 else ('B' if total >= 8 else 'C')
    diy_modifier = (q3_idx == 2 and q2 >= 5)   # Q3=C with high complexity
    return {'total': total, 'band': band, 'q2_score': q2,
            'diy_modifier': diy_modifier,
            'flags': [] if q2_none else
                     [(Q2['options'][i][0], Q2['options'][i][2])
                      for i in q2_flags]}


def result_copy(res: dict, *, n_similar: int = 0) -> dict:
    """{title, body_md, primary:(label,url), secondary:(label,url)}"""
    flags_md = '\n'.join(f"- **{f[0]}** — {f[1]}" for f in res['flags']) \
               or '_(none selected)_'
    x = len(res['flags'])

    if res['diy_modifier']:
        top = '\n'.join(f"- **{f[0]}** — {f[1]}" for f in res['flags'][:3])
        return {
            'title': "You'd rather do it yourself — here's what we'd check first",
            'body_md':
                "You would rather handle this yourself, and that is a "
                "reasonable call for a lot of businesses. Yours is not the "
                "simplest case though, so here are the things we would check "
                f"first if we were in your shoes:\n\n{top}\n\n"
                "If you want a second pair of eyes before you file, the Brand "
                "Audit covers exactly those points — and if you would rather "
                "crack on, the free search and the guides are there and they "
                "cost nothing.",
            'primary': ('Run a free trademark search', LINKS['enquiry']),
            'secondary': ('Book a Brand Audit', LINKS['audit']),
        }

    if res['band'] == 'A':
        return {
            'title': "Your brand is carrying real value, and real risk",
            'body_md':
                "Based on your answers, your name is doing serious work for "
                f"your business, and there are **{x}** things about your "
                "situation that commonly cause applications to fail or to "
                "protect less than the owner expected.\n\n"
                f"Here is what stood out:\n\n{flags_md}\n\n"
                "None of that means your name cannot be protected. It means "
                "the research matters more in your case than it would for a "
                "simple, made-up, single-product name.\n\n"
                "That is what a Brand Audit does: it tells you before you "
                "spend anything on filing whether your application is likely "
                "to succeed, which classes you actually need, and where the "
                "conflicts are. If the honest answer is that it will not "
                "succeed, we tell you that.",
            'primary': ('Request your Brand Audit', LINKS['audit']),
            'secondary': ('Book a free 15-minute consultation', LINKS['talk']),
        }

    if res['band'] == 'B':
        return {
            'title': "Worth checking before you commit",
            'body_md':
                "Your name is starting to carry real value, and there "
                f"{'is' if x == 1 else 'are'} **{x}** thing"
                f"{'' if x == 1 else 's'} in your situation worth checking "
                f"before you file.\n\n{flags_md}\n\n"
                "Plenty of businesses in your position do go on to register "
                "successfully. The risk is not that it is impossible — it is "
                "that a small problem you cannot see from the outside turns a "
                "filing into a refused application and a repeat fee.\n\n"
                "If you want certainty before spending, the audit is the "
                "cheapest insurance available.",
            'primary': ('Book a free 15-minute consultation', LINKS['talk']),
            'secondary': ('Request a Brand Audit', LINKS['audit']),
        }

    return {
        'title': "You may not need us yet — and that is a fine answer",
        'body_md':
            "Based on what you have told us, yours looks like one of the "
            "more straightforward situations. A distinctive name, a focused "
            "offering"
            + (", and no obvious conflicts showing in your sector"
               if n_similar == 0 else "")
            + ".\n\nWe are not going to tell you to buy something you do not "
            "need. Here is what we would do in your position:\n\n"
            "- Keep this report — it is your record of the ground today\n"
            "- Read the free guides on classes and what a trademark covers\n"
            "- Come back to us if any of these change: you add products or "
            "services, you start selling outside the UK, someone launches "
            "with a similar name, or you start thinking about investment or "
            "a sale",
        'primary': ('Make an enquiry any time', LINKS['enquiry']),
        'secondary': ('Browse the free guides', LINKS['enquiry']),
    }
