# The decisions behind the code

A comment like `P18 of the polish review` points at one recommendation (`P18`) of one review (`the polish review`). A
review was a working document of the project: a list of numbered recommendations, each answered yes, no or later,
with a few calls (`C1`, `C2`…) between options. The reviews themselves are private and are not published. This page
is their index: what each was about and what it decided, so a comment's reason can be followed.

How to read a code:

- The letters repeat from one review to another (`R` is in the for-everyone review and in the road plan, `S` in five
  of them), so a code is read with the tag beside it.
- A bare `row N` is a row of the reader-experience review; `row N of the decisions` is one of the twelve first
  decisions.
- A few reviews are cited by their codes alone (`D10`, `W3`); the table names them too. In `back/apps/discussion`,
  `back/apps/media` and `web/src/features/discussion`, a bare `R`, `W` or `M` code is the discussion's polish.
- A call cited by its date alone («C3 of 29 Oct 2026», «the chart rule of 1 Nov 2026», «an editorial call of 15 Nov
  2026») has its row under that date.
- `owner-provisional` (`checked: owner-provisional` in a data file, or beside a test set's answers) marks what the
  project's editor checked and a lawyer, or another specialist, has yet to read. Each is read again when one joins.
- A recommendation answered no is not built and not proposed again.

| Tag | Codes | Date | What it was about | What it decided |
|---|---|---|---|---|
| the decisions | rows 1–12 | 18 Oct 2026 | The sources, the rights, the data model, search, the use of language models, the pipeline, the roadmap. | All twelve taken, row 8 changed: there is no chat about the law; language models work only inside the pipeline. |
| the design-direction review | | 18 Oct 2026 | The tokens, the type and every screen, on a desk and a phone. | Its tokens are `web/src/shared/design/app.css`. |
| the reader-experience review | rows 1–20, seven calls | 18 Oct 2026 | Reading the law as a reader does: search, long texts, an article's page, saving, the home. | All taken: codes found by their everyday names, a long text a window at a time, saved articles on the device, the shelf of twenty codes, self-hosted fonts, a first-load budget. |
| the links review | L1–L13 | 19 Oct 2026 | Which text changes which. | All taken: one address per text from its kind and number, the links read by code from every article and weighed against the official consolidations, applied in legal time, a text's status said from what was read. |
| the discussion review | D1–D14 | 19 Oct 2026 | Comments, questions, «مفيد», voices and pictures, moderation. | All taken. The voice recorder and player stay left to right on Arabic pages; writing stays closed in production until the data-protection declaration and a lawyer's review of `/rules` and `/privacy`. |
| the discussion's polish | six fixes (F1–F6); R1–R7, W1–W8 and M1–M12 | 19 Oct 2026 | The discussion for its readers (R), writers (W) and reviewers (M): 27 recommendations. | All taken; W8 changes D3: only a newcomer's first contribution waits, the next two are looked at after publication. On 29 Oct 2026 M12's reviewers became each topic's moderators, chosen by the staff from its community. |
| the for-everyone review | R1–R16 | 19 Oct 2026 | The site for people who do not read law: its look, its words, its home. | Yes to R1–R10 and R12–R15, no to R11 (voices, Darija voice notes, Tamazight) and R16 (user testing). Built: twelve life topics, a law as a profile, checked explanations, guides, follows, share pictures, corrections. |
| the polish review | P1–P19 | 19 Oct 2026 | The bugs and rough edges. | All taken: a 14 px floor and 44 px targets, seven type tokens and one kit, everyday names in every reference, no dead end in search, find in a text, one row of actions, the about page. |
| the family plan | F1–F17 | 20 Oct 2026 | The family topic. | All taken: the texts read against their pages, the topic kit, the inheritance calculator shown before an adoul's review; never a maintenance calculator; the reform never written as law. |
| the work plan | T1–T17 | 20 Oct 2026 | The work topic. | All but T16 taken: the Labour Code and nine texts around it, the cited articles read against their pages, search that knows workers' words, four tools. |
| the housing plan | H1–H17 | 20 Oct 2026 | Housing and renting. | All taken: the code of obligations and the housing laws, the cited articles read against their pages, an official consolidation winning a same-day tie, four tools. |
| the road plan | R1–R18, Q1–Q7 | 20 Oct 2026 | The road topic. | All taken: the decrees and orders a driver lives by, the points table, the official French, the tools, scenes and signs. |
| the road tools review | 58 recommendations in fifteen lettered groups (the code cites A1–A4, C1, F1–F10, G1–G3, J1–J6, M1, N1–N2, P1–P4, Q1–Q3, R1–R2, S1–S6, T1–T6, U1–U2, V1–V2 and X1–X3), calls K1–K7 | 24 Oct 2026 | The road topic rebuilt around the moment something happens. | All taken: the page opens on «شنو وقع ليك؟» with the emergency in a red band, journeys answer first, tools answer on top, riders and pedestrians get their doors, a reviewer's desk. No emergency number is shown without an official source. |
| the consumer plan | A, D, J, K, N, S and T rows | 24 Oct 2026 | The consumer topic. | All taken as proposed: doors by how the reader bought, journeys after a purchase, letters, checklists, search questions. |
| the performance audit | S1–S23 | 24 Oct 2026 | Twenty-three findings on speed and load. | Yes to all but S8 and S21–S23 (later): no query inside a loop, a shared cache, answers kept by generation, cache headers, query ceilings in the tests. |
| the search plan | B1–B30 | 24 Oct 2026 | Search, measured on a pilot. | Taken month by month: a test set and its judge, logs that teach, citations in every form, Latin-letter Darija, meaning search with a local model; it stays on PostgreSQL (B26) and no language model runs at query time (B29). |
| the constitution review | C1–C12 | 25 Oct 2026 | Morocco's constitutions since independence. | All taken: the six constitutions with their preambles, and their short history drawn only from the texts. |
| the Moroccan-design review | U1–U20 | 25 Oct 2026 | A Moroccan shape for the site. | All taken: the horseshoe arch for the ways in, a law's page that starts with the law, one sheet a finger pulls down, the public holidays inside deadlines, the Hijri dates, the article lit on its printed page. |
| the road-signposted review | A1–A17, C1–C2 | 26 Oct 2026 | The road topic's page in the road's own language. | All taken: Morocco's own day for every date, only numbers an official page gives, the tools as instruments, the accident page kept offline. |
| the family-papers review | G1–G16, C1 | 26 Oct 2026 | The family topic by the papers its passages end on. | All taken: each door led by the mark of the office where it ends, one question in the family's plural, the reform as four stops, a number hidden until its page is kept. |
| the work-counted review | E1–E18, C1–C2 | 26 Oct 2026 | The work topic by its numbers. | All taken: each door led by its number on a punch card, the doors in a working life's order, three instruments (the dismissal's staircase, the payslip, the social-security days). |
| the consumer-receipt review | | 26 Oct 2026 | The consumer topic around the receipt. | Doors led by a price tag, a receipt of one purchase's rights with their last days, kept on the phone and waiting for review. |
| the land review | M1–M19, C1–C3 | 26 Oct 2026 | The land topic. | All taken: doors led by the plot as a surveyor draws it, what kind of land the reader holds, the Bulletin's land texts found by commune, property, title number or name. |
| the tax review | T1–T23, C1–C4 | 26 Oct 2026 | The tax code and the tax topic. | All taken: the tax code with each finance law's change dated, the topic's deadlines, journeys and nine tools, all waiting for review. |
| the finance-bill review | P1–P23, C1–C4 | 26 Oct 2026 | The 2027 finance bill. | All taken: a bill is never law; what it would change is kept as proposals, never applied; its budget checked; what was said set beside what the text says. |
| the bill-page review | V1–V16, C1–C3 | 26 Oct 2026 | The bill's page. | All taken: the changes as data drawn as amendment lines, the reader's own section open first. |
| the bill-story review | Y1–Y14, C1–C4 | 26 Oct 2026 | The bill told as a news graphic. | All taken: the guess, the curve of the monthly gain at every salary, four people over five years; what people say, each item dated, linked and kept with its hash (`docs/rules.md`). |
| the bill-rows rewrite | | 27 Oct 2026 | The bill page's salaried rows. | Each row in one plain sentence, today's figure beside the bill's and the reader's own. |
| the health review | S1–S20, C1–C5 | 27 Oct 2026 | The health topic. | All taken: one question on the reader's cover, doors led by a medicine's label, the texts the topic cites read against their pages; a version still to come is never read as today's. |
| the papers review | | 27 Oct 2026 | Identity and civil-status papers. | Doors led by the identity card, nine journeys, five tools waiting for review. |
| the business review | | 27 Oct 2026 | Running a business. | Doors led by the company's stamp, nine journeys, four tools waiting for review. |
| the justice review | | 27 Oct 2026 | The police, the courts, lawyers and legal aid. | Doors led by the court file, the custody band, four tools waiting for review, written on the codes in force. |
| the digital review | | 27 Oct 2026 | Personal data, online offences, e-signatures, copyright. | Doors led by a chat message, nine journeys, four tools waiting for review. |
| the read-and-trusted review | N1–N17, C1–C3 | 27 Oct 2026 | Reading the law and trusting what is shown. | Yes to N1 and N3–N17, N2 later: test accounts off the public site, the consolidation's day shown, every law's address with its own head, no OCR inside a request, French law in its own type. |
| the Bulletin-to-1956 review | Z1–Z14 | 27 Oct 2026 | The Arabic Bulletin from 1956 to 2018, read from its scans. | All but Z2 and Z6 taken: every page read, the special texts too. |
| the second-archive-run review | Z15–Z27, C1–C4 | 29 Oct 2026 | Finishing the 1956–2018 run. | All taken: laws and regulations first, code before a model wherever code can decide. Z27 was added during the run: an issue's pages numbered by the offset its own contents bear out. |
| the phone-test review | UX1–UX16, C1–C3 | 29 Oct 2026 | The live site tested on a phone. | All but UX2 (later) taken: the library in the phone's bar, Latin-letter Darija, a search that says nothing matched, 44 px targets, the accessibility checker in the end-to-end tests. |
| the search's marks | H1–H6 | 29 Oct 2026 | The searched words in the law. | The words a search found are lit in the text it opens. |
| the social layer | C1–C4, cited by date | 29 Oct 2026 | The discussion as posts and comments in each topic's place, checked before they are published, with moderators from each topic's community. | All four calls as recommended: C1 text only (voices and pictures off at launch); C2 a post waits for a person when the check cannot run; C3 an article's page lists the posts that cite it; C4 a post is a question or a post. |
| the where-it-trips review | PX1–PX40, C1–C3 | 31 Oct 2026 | Where a reader trips. | All taken; words between quotes are searched as typed. |
| the blog-first-post review | B1–B10 | 31 Oct 2026 | The blog's first posts and their order. | All taken: ten posts, built in the order chosen. |
| the places review | PL1–PL24, C1–C6 | 1 Nov 2026 | The countries and places the Bulletin names. | All taken, PL18 later: `/places`, its maps and its posts. |
| the chart rule | | 1 Nov 2026 | How a chart reads on an Arabic page. | Charts run left to right on every page, the percent sign to the right of its number, a legend for coloured kinds (`docs/design.md`, «Languages and direction»). |
| the Bulletin-from-No.-1 review | H1–H11, C1–C3 | 1 Nov 2026 | The Bulletin from its first issue, 1913–1955. | All taken: the old issues read; the texts only the French edition holds given an Arabic translation, marked as one. |
| the mended-Bulletin review | FX1–FX12, C1–C3 | 2 Nov 2026 | The faults in the Bulletin's data. | All taken: copies folded, twins merged, the faults counted and mended. |
| the MCP review | MC1–MC25, C1–C8 | 3 Nov 2026 | The law in AI assistants, through MCP. | All taken: the site gives the law with its source and standing and writes no answer; five read-only tools; open without an account, the sign-in kept dormant. |
| the first-principles review | S1–S24, C1–C6 | 5 Nov 2026 | The law measured whole, and the stories in it. | Sixteen taken, S4 and S5 no, six later: the stories became blog posts. |
| the posts-from-No.-1 review | BH1–BH19, C1–C6 | 6 Nov 2026 | The posts counted again from 1913. | BH1–BH17 taken (BH1 later undone), BH18 and BH19 later: `/places` from 1913, the old names of places, the posts' figures from No. 1. |
| the hard-moment review | HM1–HM44, C1–C2 | 7 Nov 2026 | The site in a reader's hard moment, on a slow phone. | Most taken, HM24 no, five later: the first words fast on a slow network, the law first, fewer requests. |
| the search-engines review | IX1–IX17, C1–C4 | 9 Nov 2026 | Being found by search engines. | IX1–IX5, IX7–IX11, IX13 and IX14 taken: every law's address drawn on the server, true 404s and redirects, sitemaps opened in waves, drafts indexed as marked; training crawlers kept out, answer bots let in. |
| the famous-articles review | F1–F11, C1–C3 | 9 Nov 2026 | Articles people know by their number. | All taken: a bare number such as 490 opens the article people mean, with the name the public debate gave it. |
| the every-code review | LB1–LB13, C1–C4 | 9 Nov 2026 | The library: every code and every issue within reach. | All taken: one box that reads a number, a page, a reference or a day; the codes in their branches; the issues as a compact map. |
| the readers review | RD1–RD24, C1–C4 | 9 Nov 2026 | The codes people read most. | All taken: their text-layer slips found against the Bulletin's page images, commencement clauses and repeals read, the official French where it exists. |
| the library-search review | W1–W11, C1–C5 | 10 Nov 2026 | Reaching any code, law or issue from whatever a reader knows of it. | All taken: one reader behind the library's box, the header and the search page; the Hijri months from the Bulletin's own dates. |
| the open-source audit | OP1–OP56, C1–C7 | 10 Nov 2026 | The code before it is opened. | All taken and built. |
| the inheritance review | IR1–IR30, C1–C7 | 14 Nov 2026 | The inheritance calculator. | All but IR8, IR10, IR17 and IR29 taken: the compulsory bequest as the Court of Cassation reads it, the adoul's table, the questions in the law's order. |
| the Chamber-vote update | | 15 Nov 2026 | The finance bill's vote in the Chamber of Representatives. | Each vote and amendment as the committee's report prints it, the report's page on each row. |
| the said-once call | | 15 Nov 2026 | Where the site says what the AI did and what no one has reviewed yet. | Said once, under every page and in full on `/about`; the pages themselves no longer say it. Cited as «an editorial call of 15 Nov 2026». |
| the analytics review | AN1–AN26, C1–C5 | 15 Nov 2026 | What the site measures about its own use. | All taken, AN26 later: tasks are counted, never people; every measure declared with its question and its end date; nothing leaves the server; the web server's log without query strings. |
| the access review | RQ1–RQ34, C1–C5 | 16 Nov 2026 | The database and an API for outside programs. | RQ1–RQ31 taken, RQ32–RQ34 later: both are given on request, to an account the staff accepted; one key an access with its own limits, counted per access and day and never by what was asked; a small versioned API over the assistants' services; a monthly edition under ODbL with every version, marked by its kind. |
| the account-and-desk review | DK1–DK24, C1–C5 | 16 Nov 2026 | The account page, and where requests for access are answered. | All taken: the account as two pages of rows; a holder's page that opens on where the account stands; a desk in the site for a superuser, with every request and access, their use, the editions and a log of every act. |
