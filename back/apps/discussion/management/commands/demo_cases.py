"""The demo's second part (30 Oct 2026): every topic with posts, and every state a reader, a writer, a moderator or staff
meets, to try the discussion by hand. People, cases and stories are invented; what the answers say of the law stays
general and hedged. Run by seed_demo_talk (a dev database only).

Each post: (topic, author, kind, title, body, about, quote, comments). A comment: (author, body, reply to the comment
at this index or None). `accept` marks the comment at that index «أفادني»; `votes` gives the post that many «مفيد»."""
from datetime import timedelta

from django.utils import timezone

from apps.discussion.models import Check, Contribution, Follow
from apps.discussion.services import compose, counters, reports, review, votes

POSTS = [
    # ── road ──
    dict(topic='road', who='youssef', kind='question', title='شحال الغرامة على السرعة فوق 20 كلم/س؟',
         body='تشدّيت فالرادار بـ 87 فبلاصة 60. شحال الغرامة وواش كتنقص ليا النقط؟', about='/ma/loi/52-05/art_184',
         comments=[('rachid', 'كتختلف حسب الفرق بين السرعة المسجلة والسرعة المسموح بها. شوف المادة 184 والمواد اللي من بعدها، وأداة السرعة فموضوع الطريق كتحسبها ليك.', None),
                   ('youssef', 'شكرا، الأداة فادتني.', 0)], accept=0, votes=4),
    dict(topic='road', who='loubna', kind='post', title='نصيحة ملي كتوقع ليك حادثة بلا ضحايا',
         body='عمرو المحضر الودي (constat amiable) فالبلاصة وصورو الطوموبيلات قبل ما تحركوهم. هادشي سهّل عليا التعويض بزاف.',
         comments=[('ayoub', 'واش خاصك تعلم شركة التأمين فشحال من يوم؟', None),
                   ('loubna', 'فالعقد ديالي كان مكتوب 5 أيام، شوف العقد ديالك.', 0)], votes=7),
    dict(topic='road', who='hind', kind='question', title='Permis à points : comment récupérer mes points ?',
         body='Il me reste 6 points sur mon permis. Est-ce qu’ils reviennent avec le temps ou faut-il suivre une formation ?',
         about='/ma/loi/52-05/art_99', comments=[], votes=1),
    # ── consumer ──
    dict(topic='consumer', who='karim', kind='question', title='شريت أونلاين وبغيت نرجع السلعة',
         body='شريت تيليفون من موقع، ووصلني ما عجبنيش. واش عندي الحق نرجعو بلا سبب؟', about='/ma/loi/31-08/art_36',
         quote='', comments=[('amina', 'فالبيع عن بعد، القانون 31.08 كيعطي أجل للتراجع. المادة 36 كتهضر عليه، وكاين استثناءات.', None)],
         accept=0, votes=5),
    dict(topic='consumer', who='naima', kind='post', title='تجربتي مع الضمانة ديال التلاجة',
         body='التلاجة خسرات بعد 4 شهور، المحل قالي سير للماركة. كتبت ليهم رسالة مضمونة وذكرت ليهم الضمانة القانونية، ورجعوها ليا مصلحة.',
         comments=[('said', 'شنو كتبتي فالرسالة بالضبط؟', None), ('naima', 'التاريخ، الفاتورة، والعطب، وطلبت الإصلاح ولا التبديل.', 0)],
         votes=9),
    # ── land ──
    dict(topic='land', who='omar', kind='question', title='أرض ماشي محفظة: كيفاش نثبت الملكية؟',
         body='ورثنا أرض فالبادية بلا رسم عقاري، عندنا غير عقد عرفي قديم. شنو هي الخطوات؟', about='/ma/loi/39-08/art_2',
         comments=[('hassan', 'كاين التحفيظ العقاري، وكيبدا بمطلب التحفيظ عند المحافظة. العقد العرفي والشهود كيعاونو فالملف.', None),
                   ('omar', 'واش خاصني مهندس طوبوغرافي من الأول؟', 0)], votes=3),
    dict(topic='land', who='brahim', kind='question', title='رخصة البناء ديال طابق زايد',
         body='بغيت نزيد طابق فوق الدار. واش خاصني رخصة جديدة ولا تكفي الرخصة القديمة؟', comments=[], votes=0),
    # ── health ──
    dict(topic='health', who='samira', kind='question', title='CNOPS ولا CNSS: شكون غادي يعوض ليا؟',
         body='أنا موظفة، وسمعت بلي التعويض غادي يتبدل. واش الملفات اللي صيفطت لـ CNOPS غادي تضيع؟', about='/ma/loi/65-00/art_2',
         comments=[('zineb', 'الانتقال معلن فموضوع الصحة مع تاريخه. الملفات اللي تصيفطات قبل كتبقى كتعالج، ولكن شوف الإعلان الرسمي ديال الصندوق.', None)],
         accept=0, votes=6),
    dict(topic='health', who='ilham', kind='question', title='المرض المزمن والتعويض 100%',
         body='بابا عندو القصور الكلوي. واش كيدخل فلائحة الأمراض اللي كتعوض كاملة؟', anonymous=True,
         comments=[('rajae', 'القصور الكلوي المزمن من الأمراض الطويلة والمكلفة. الأداة ديال الأمراض المزمنة فموضوع الصحة كتقول ليك.', None)],
         votes=2),
    # ── papers ──
    dict(topic='papers', who='anas', kind='question', title='Nationalité marocaine pour mon fils né à l’étranger',
         body='Mon fils est né en France d’une mère marocaine et d’un père français. Est-il marocain ?', about='/ma/dahir/1-58-250/art_6',
         comments=[('asmae', 'Depuis la réforme de 2007, la mère transmet la nationalité marocaine. Voir l’article 6 du code de la nationalité.', None)],
         accept=0, votes=4),
    dict(topic='papers', who='driss', kind='question', title='ضاعت ليا البطاقة الوطنية',
         body='ضاعت ليا البطاقة. شنو الوراق اللي خاصني نجيب للكوميسارية؟', comments=[], votes=0),
    # ── business ──
    dict(topic='business', who='tarik', kind='question', title='المقاول الذاتي ولا الشركة ذات المسؤولية المحدودة؟',
         body='بغيت نبدا مشروع صغير فالتجارة الإلكترونية. شنو أحسن: مقاول ذاتي ولا SARL؟', about='/ma/loi/5-96/art_49',
         comments=[('mustapha', 'المقاول الذاتي ساهل فالبداية وعندو سقف ديال رقم المعاملات. الشركة كتحمي الذمة ديالك ولكن فيها مصاريف.', None),
                   ('tarik', 'شحال هو السقف؟', 0), ('mustapha', 'كاين فموضوع المقاولة، الأداة ديال الأشكال كتقول ليك.', 1)],
         accept=0, votes=8),
    dict(topic='business', who='jamal', kind='question', title='شيك بلا رصيد توصلت بيه',
         body='كليان عطاني شيك وطلع بلا رصيد. شنو ندير قبل ما يفوت الأجل؟', about='/ma/loi/15-95/art_316', comments=[], votes=1),
    # ── digital ──
    dict(topic='digital', who='houda', kind='question', title='شركة كتعيط ليا كل نهار',
         body='شركة كتبيع ليا عروض فالتيليفون كل نهار. واش نقدر نطلب يحيدو الرقم ديالي؟', about='/ma/loi/9-08/art_8',
         comments=[('amina', 'القانون 09.08 كيعطيك الحق تعترض على استعمال المعطيات ديالك فالإشهار. الرسالة جاهزة فموضوع الأنترنت.', None)],
         accept=0, votes=5),
    dict(topic='digital', who='reda', kind='question', title='Diffamation sur Facebook',
         body='Quelqu’un publie de fausses accusations contre moi sur Facebook. Quel texte s’applique ?', about='/ma/loi/88-13/art_85',
         comments=[], votes=2),
    # ── tax ──
    dict(topic='tax', who='othmane', kind='question', title='الضريبة على الكرا ديال شقة وحدة',
         body='كنكري شقة وحدة بـ 3000 درهم. شحال خاصني نخلص ديال الضريبة وإمتى نصرح؟', about='/ma/code/cgi/art_73',
         comments=[('karim', 'كاين المعدل الخاص بالدخول العقارية، والتصريح كيكون قبل أجل محدد فالعام. الأداة ديال الكرا فموضوع الضرائب كتحسب.', None)],
         votes=3),
    # ── justice ──
    dict(topic='justice', who='abdellah', kind='question', title='خويا فالحراسة النظرية: واش يقدر يتصل بمحامي؟',
         body='شدّو خويا البارح. واش عندو الحق فمحامي دابا؟ وشحال كتدوم الحراسة النظرية؟', about='/ma/loi/22-01/art_66',
         comments=[('latifa', 'المادة 66 من المسطرة الجنائية كتنظم الحراسة النظرية والاتصال بالمحامي. الأداة ديال ساعات الحراسة فموضوع الشرطة والمحاكم.', None)],
         accept=0, votes=7, anonymous=True),
    # ── work ──
    dict(topic='work', who='nabil', kind='question', title='فترة التجربة: شحال كتدوم؟',
         body='خدام فشركة هادي شهرين، وقالو ليا مازال فالتجربة. شحال الأقصى ديال فترة التجربة؟', about='/ma/loi/65-99/art_16',
         comments=[], votes=0),
    # ── family ──
    dict(topic='family', who='ghizlane', kind='question', title='الطلاق للشقاق: شحال كياخد ديال الوقت؟',
         body='دخلت دعوى الشقاق هادي 4 شهور. واش كاين أجل قانوني للحكم؟', about='/ma/loi/70-03/art_84',
         comments=[('bouchra', 'كاين أجل كتنص عليه المدونة للبت فالشقاق، ولكن فالواقع كيتأثر بمحاولات الصلح. سولي كتابة الضبط.', None)],
         votes=2),
    # ── general ──
    dict(topic='general', who='aziz', kind='question', title='فين نلقى النص الرسمي ديال قانون؟',
         body='بغيت نقرا قانون بالنسخة الرسمية ديالو. واش اللي هنا هو نفس اللي فالجريدة الرسمية؟',
         comments=[('sanae', 'كل مادة فيها الطابع ديال العدد والصفحة فالجريدة الرسمية، وتقدر تفتح الصفحة المطبوعة.', None)],
         accept=0, votes=3),
    dict(topic='general', who='nawal', kind='post', title='شكرا على هاد الموقع',
         body='أول مرة نلقى القوانين مكتوبة بطريقة نفهمها. الله يجازيكم.', comments=[('adil', 'متفق، خصوصا الأدوات.', None)], votes=6),
]

# A comment with many replies (30 Oct 2026): a moderator's answer, then a conversation under it. Each reply: (author,
# body, the reply it answers, by index; 0 is the first answer). `jamal`'s waits for a moderator (a phone number) and
# `khalid`'s is removed.
THREAD = dict(
    who='siham', title='مول الدار باع الدار وبغا يخرجني فشهر',
    body='كنكري هاد الدار هادي 7 سنين، ومول الدار باعها لواحد آخر. المالك الجديد قالي عندك شهر وتخوي. واش هادشي قانوني؟',
    about='/ma/loi/67-12/art_45',
    answer=('khadija', 'بيع الدار ما كيفسخش عقد الكراء بوحدو: المالك الجديد كيدخل فبلاصة القديم، والعقد كيبقى. إلا بغا '
            'يخرجك خاصو يتبع الإجراءات اللي فالقانون 67.12 ويكون عندو سبب من الأسباب اللي كينص عليها، ماشي غير بالهضرة.'),
    replies=[
        ('siham', 'شكرا بزاف. ولكن هو كيقول بلي العقد ديالي كان مع المالك القديم وماشي معاه.', 0),
        ('khadija', 'العقد كيتنقل مع الملك. احتفظي بالعقد ووصولات الكرا كاملين.', 1),
        ('younes', 'نفس الشي وقع لخويا فالدار البيضاء، والمحكمة رفضات الإفراغ.', 0),
        ('siham', 'واش تقدر تقولي شحال دامت القضية؟', 3),
        ('younes', 'تقريبا 8 شهور، وبقى خويا ساكن طول هاد المدة.', 4),
        ('malika', 'وإلا كان العقد غير شفوي، بلا ورقة؟', 0),
        ('khadija', 'الكراء الشفوي صعيب يتثبت. الوصولات والتحويلات البنكية كيعاونو. ولكن هادي حالة أخرى، الأحسن تسولي '
                    'محامي ولا مكتب المساعدة فالمحكمة.', 6),
        ('aziz', 'خاص المالك الجديد يصيفط إنذار مكتوب، ماشي غير يجي يهضر.', 0),
        ('siham', 'ما صيفط والو، غير جا للباب وهضر.', 8),
        ('sanae', 'إذن ما تخرجيش حتى يوصلك شي حاجة رسمية، وحتى داك الساعة تقدري تجاوبي.', 9),
        ('hind', 'En résumé : la vente ne met pas fin au bail ; le nouveau propriétaire reprend le contrat tel quel.', 0),
        ('rachid', 'صحيح، وهادي قاعدة معروفة فالكراء.', 11),
        ('brahim', 'ولكن إلا بغا يسكن فيها هو، ماشي عندو الحق؟', 0),
        ('khadija', 'كاين حالات كيعطي فيها القانون للمالك الحق يسترجع المحل باش يسكن فيه، ولكن بشروط وأجل وأحيانا تعويض. '
                    'شوف المادة 45 وما بعدها.', 13),
        ('brahim', 'مفهوم، يعني ماشي فشهر.', 14),
        ('khadija', 'بالضبط، ماشي فشهر.', 15),
        ('ayoub', 'تقدري تمشي لمكتب المساعدة القضائية فالمحكمة، كيوجهوك.', 0),
        ('latifa', 'المساعدة القضائية كاينة حتى فقضايا الكراء؟', 17),
        ('ayoub', 'إلا كانت شروط الدخل متوفرة، إيه. سولي فكتابة الضبط.', 18),
        ('nabil', 'أنا كنت فنفس الحالة وتفاهمت مع المالك الجديد على تعويض وخرجت براحتي. حتى الاتفاق حل.', 0),
        ('siham', 'شحال عطاك؟', 20),
        ('nabil', 'ما نقدرش نقول الرقم، ولكن تفاوضي وما تتسرعيش.', 21),
        ('ghizlane', 'الاتفاق مزيان ولكن خاصو يكون مكتوب وموقع.', 20),
        ('meryem', 'Gardez une copie de chaque reçu de loyer, c’est votre preuve principale.', 0),
        ('driss', 'واش المالك الجديد يقدر يزيد فالكرا دابا؟', 0),
        ('khadija', 'الزيادة عندها قواعدها حتى هي، ماشي حيت تبدل المالك. كاين أسئلة على الزيادة فهاد الموضوع.', 25),
        ('othmane', 'كنصح تكتبي ليه رسالة مضمونة وتقولي ليه بلي العقد مازال ساري.', 0),
        ('siham', 'فكرة مزيانة، غادي ندير هاكا.', 27),
        ('jamal', 'إلا بغيتي محامي فهاد الشي عيطي ليا 0600000000.', 0),
        ('khalid', 'هادو اللي كيكريو ديما بغاو يبقاو فابور فديور الناس.', 0),
        ('bouchra', 'الله يسهل عليك أختي.', 0),
        ('siham', 'شكرا لكم كاملين، فهمت دابا شنو خاصني ندير. غادي نحتفظ بالوصولات ونستنى إلا جاني شي إنذار.', 0),
        ('adil', 'بالتوفيق، وعاودي لينا شنو وقع.', 32),
    ],
    votes={0: 12, 3: 4, 14: 6, 11: 3, 20: 2, 27: 2},
)


def long_thread(cmd) -> Contribution:
    people = cmd.people
    post = compose.contribute(people[THREAD['who']], path='/talk/housing', kind='question', title=THREAD['title'],
                              body=THREAD['body'], about=THREAD['about'])
    cmd.when(post, 2)
    who, body = THREAD['answer']
    made = [compose.contribute(people[who], parent_id=post.pk, body=body)]
    cmd.when(made[0], 1.95)
    for k, (who, body, to) in enumerate(THREAD['replies']):
        c = compose.contribute(people[who], parent_id=made[to].pk, body=body)
        cmd.when(c, 1.9 - k * 0.055)
        made.append(c)
    for k, n in THREAD['votes'].items():
        cmd.vote(made[k], n)
    votes.accept(people[THREAD['who']], made[0].pk)
    rude = next(c for c in made if c.author_id == people['khalid'].pk)
    review.remove(people['khadija'], rude.pk, 'respect', 'تعميم مسيء')
    return post


# What moderators meet, and what an author sees of it (each a post written then put in its state).
STATES = [
    # (name, topic, author, kind, title, body)
    ('held_pattern', 'housing', 'jamal', 'post', 'شقة للكراء فحي الرياض',
     'عندي شقة للكراء، 3 بيوت، اللي مهتم يعيط ليا 0600000002.'),
    ('held_check', 'family', 'mehdi', 'post', 'رأيي فالنساء والمدونة',
     'هاد المدونة دارتها نساء حاقدات على الرجال، وكل واحدة كتطلق كتستاهل اللي جاها.'),
    ('returned_sent', 'justice', 'soukaina', 'question', 'جارنا اللي شدوه',
     'جارنا فالطابق الرابع، عمو بوشعيب، شدوه البوليس على الشيكات. شحال غادي ياخد؟'),
    ('unavailable', 'work', 'ismail', 'question', 'الساعات الإضافية فالمعمل',
     'كنخدم 10 ساعات فالنهار وكيخلصوني 8. واش هادشي قانوني؟'),
    ('sent_back', 'consumer', 'kawtar', 'post', 'محل التيليفونات اللي نصب عليا',
     'محل التيليفونات اللي فالسوق ديال الحومة، مولاه سميتو الحاج فلان الفلاني، باعني تيليفون مسروق، والبوليس شدوه مني.'),
    ('redacted', 'land', 'wafae', 'question', 'شكون يعرف مهندس طوبوغرافي مزيان؟',
     'خاصني مهندس للتحفيظ فإقليم تارودانت، اللي عندو رقم يصيفطو ولا يعيط 0600000003.'),
    ('hidden', 'digital', 'hicham', 'post', 'هادي اللي نشرات تصاوري',
     'البنت اللي نشرات تصاوري سميتها فلانة الفلانية، ساكنة فالحومة ديالنا، وهادا هو الحساب ديالها، قولو ليها تحيدهم.'),
    ('reported', 'business', 'khalid', 'post', 'خدمات المحاسبة بثمن مناسب',
     'كنقدم خدمات المحاسبة للمقاولين الذاتيين، التصريح الضريبي بـ 200 درهم فقط.'),
    ('removed_with_replies', 'road', 'said', 'post', 'البوليس ديال الطرق',
     'البوليس ديال الطرق كاملين كياكلو الرشوة، ما كاين لاش تخلص المخالفة.'),
    ('deleted_with_replies', 'family', 'latifa', 'question', 'واش نقدر نسافر بولدي بلا إذن باباه؟',
     'طليقي ما بغاش يعطي الإذن. بغيت نسافر بالولد عند ماما فالصيف.'),
    ('duplicate', 'consumer', 'reda', 'question', 'Rendre un article acheté en ligne',
     'J’ai acheté une chaise en ligne, elle ne me plaît pas. Puis-je la renvoyer ?'),
    ('edited', 'housing', 'meryem', 'question', 'Le propriétaire garde la caution',
     'J’ai quitté l’appartement propre, mais le propriétaire refuse de rendre la caution. Que faire ?'),
]


MODERATORS = {'hamid': ['/talk/family'], 'khadija': ['/talk/housing', '/talk/work'],
              'karim': ['/talk/justice', '/talk/tax'], 'amina': ['/talk/consumer', '/talk/digital'],
              'omar': ['/talk/land', '/talk/papers'],
              'zineb': ['/talk/road', '/talk/health', '/talk/business', '/talk/general']}


def run(cmd) -> dict:
    """The posts above, the long thread, then the states; returns {name: post} for the thread and the states."""
    people, staff = cmd.people, cmd.staff
    for i, p in enumerate(POSTS):
        post = compose.contribute(people[p['who']], path=f"/talk/{p['topic']}", kind=p['kind'], title=p['title'],
                                  body=p['body'], about=p.get('about', ''), quote=p.get('quote', ''),
                                  anonymous=p.get('anonymous', False))
        days = 6 - i * 0.25
        cmd.when(post, days)
        made = []
        for k, (who, body, to) in enumerate(p['comments']):
            parent = made[to].pk if to is not None else post.pk
            c = compose.contribute(people[who], parent_id=parent, body=body)
            cmd.when(c, days - 0.1 * (k + 1))
            made.append(c)
        if p.get('accept') is not None and made and made[p['accept']].author_id != post.author_id:
            votes.accept(people[p['who']], made[p['accept']].pk)
        for c in made[:1]:
            cmd.vote(c, 2)
        cmd.vote(post, p.get('votes', 0))

    # Moderators from each topic's community, appointed by staff: every topic has one.
    for who, paths in MODERATORS.items():
        review.appoint(staff, people[who], paths)
    out = {'long_thread': long_thread(cmd)}
    for name, topic, who, kind, title, body in STATES:
        out[name] = compose.contribute(people[who], path=f'/talk/{topic}', kind=kind, title=title, body=body)
    now = timezone.now()

    def held(c, reasons, outcomes):
        Contribution.objects.filter(pk=c.pk).update(held_at=now - timedelta(hours=3), held_reasons=reasons)
        for k, (outcome, rule, failure) in enumerate(outcomes):
            # A returned post is not kept: only its last look, sent as it was, belongs to the contribution.
            Check.objects.create(user=c.author, contribution=c if k == len(outcomes) - 1 else None, outcome=outcome,
                                 rule=rule, failure=failure, model='demo', prompt_version='demo')
        c.refresh_from_db()
        counters.around(c)

    # The model's verdicts are the demo's own (model 'demo'): no model was asked.
    held(out['held_check'], ['check_respect'], [('hold', 'respect', '')])
    held(out['returned_sent'], ['check_privacy'], [('return', 'privacy', ''), ('return', 'privacy', '')])
    held(out['unavailable'], ['check_unavailable'], [('unavailable', '', 'timeout')])
    held(out['sent_back'], ['check_privacy'], [('hold', 'privacy', '')])
    review.send_back(staff, out['sent_back'].pk, 'احذف اسم مول المحل والحي، وخلي غير شنو وقع ليك.')
    redact_at = out['redacted'].body.index('0600000003')
    review.redact(people['omar'], out['redacted'].pk, [[redact_at, redact_at + len('0600000003')]],
                  'رقم هاتف')
    for who in ('loubna', 'ayoub', 'said'):
        reports.file(people[who], out['hidden'].pk, reason='exposing')
    for who in ('naima', 'tarik'):
        reports.file(people[who], out['reported'].pk, reason='soliciting', details='كيعرض خدماتو بالثمن')
    for k, who in enumerate(('jamal', 'youssef')):
        compose.contribute(people[who], parent_id=out['removed_with_replies'].pk,
                           body=['ماشي كاملين، ما تعممش.', 'إلا عندك دليل على الرشوة بلغ عليه.'][k])
    review.remove(people['zineb'], out['removed_with_replies'].pk, 'respect', 'تعميم مسيء')
    review.appeal(people['said'], contribution_id=out['removed_with_replies'].pk,
                  text='ما قصدتش نسب حتى واحد، كنحكي على تجربتي.')
    review.pause(people['zineb'], out['removed_with_replies'].pk, days=7, rule='respect', note='ثاني مرة')
    compose.contribute(people['ghizlane'], parent_id=out['deleted_with_replies'].pk,
                       body='خاصك إذن من القاضي إلا الأب ما بغاش. سولي فمحكمة الأسرة.')
    compose.delete(people['latifa'], out['deleted_with_replies'].pk)
    first = Contribution.objects.filter(discussion__path='/talk/consumer', kind='question', parent=None) \
        .exclude(pk=out['duplicate'].pk).order_by('created_at').first()
    review.duplicate(people['amina'], out['duplicate'].pk, first.pk, 'نفس السؤال')
    compose.edit(people['meryem'], out['edited'].pk,
                 out['edited'].body + ' J’ai les photos de l’état des lieux et le reçu de la caution.')
    review.trust(people['khadija'], out['edited'].pk, True, 'تكتب بعناية')

    # The tester's own corner: a question others answered, one comment marked, a topic followed (notices to read).
    tester = cmd.people['tester']
    q = compose.contribute(tester, path='/talk/housing', kind='question', title='واش المكري يقدر يدخل للدار بلا إذن؟',
                           body='مول الدار كيدخل للشقة ملي كنكون خدامة، عندو الساروت. واش هادشي قانوني؟',
                           about='/ma/loi/67-12/art_45')
    a1 = compose.contribute(people['khadija'], parent_id=q.pk,
                            body='الشقة المكراة فالاستعمال ديالك، وماشي من حقو يدخل بلا إذنك إلا فحالات استثنائية. تقدري تبدلي القفل.')
    compose.contribute(people['meryem'], parent_id=q.pk, body='Gardez une trace écrite : envoyez-lui un message lui demandant d’arrêter.')
    votes.accept(tester, a1.pk)
    Follow.objects.get_or_create(user=tester, path='/talk/family')
    compose.contribute(people['salma'], path='/talk/family', kind='question', title='النفقة ملي الأب خدام فالخارج',
                       body='راجلي خدام فإيطاليا وما كيصيفطش النفقة. كيفاش نطالب بيها؟')
    return out
