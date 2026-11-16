"""Demo explanations for the screenshots of the for-everyone review (a dev database only: it refuses to run without DEBUG).
Run after seed_demo_talk (it uses its demo-* people). Every sentence restates what the article it names says; a
person still has to write and check the real ones. Running it again replaces what it made."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.explain.models import Explanation
from apps.explain.services import explanations

RENT = '/ma/loi/67-12'
ITEMS = [
    # (path, register, author, headline, body, sources, checked)
    (RENT, 'ar', 'salma', '',
     'ينظّم كراء السكن والمحلات المعدة للاستعمال المهني: عقد الكراء والتزامات الطرفين، مراجعة الكراء والزيادة فيه، '
     'تولية الكراء والتخلي عنه، وإنهاء العقد وفسخه.', [], True),
    (f'{RENT}/art_34', 'ar', 'salma', '',
     'لا تتجاوز الزيادة في الكراء 8% إذا كان المحل للسكن، و10% إذا كان للاستعمال المهني (مكتب، عيادة…). ولا تكون '
     'الزيادة إلا بعد مرور ثلاث سنوات على الأقل من تاريخ العقد أو من آخر مراجعة (المادتان 32 و33).',
     [f'{RENT}/art_32', f'{RENT}/art_33'], True),
    (f'{RENT}/art_34', 'darija', 'youssef', '',
     'مول الدار ما يقدرش يزيد فالكرا كثر من 8% إلا كانت الدار للسكنى، و10% إلا كان المحل للخدمة (مكتب، عيادة…). '
     'والزيادة ما كتكونش حتى تدوز 3 سنين على الأقل من العقد ولا من آخر زيادة (المادتان 32 و33). انتبه: إلا كان الكرا '
     '400 درهم فالشهر ولا أقل، المحكمة تقدر تحكم بزيادة حتى 50% (المادة 35).',
     [f'{RENT}/art_32', f'{RENT}/art_33', f'{RENT}/art_35'], True),
    (f'{RENT}/art_34', 'fr', 'salma', '',
     "La hausse du loyer ne peut pas dépasser 8 % pour un logement et 10 % pour un local à usage professionnel (bureau, "
     "cabinet…). Elle n'est possible qu'au moins trois ans après le contrat ou la dernière révision (articles 32 et 33). "
     "Si le loyer ne dépasse pas 400 dirhams par mois, le tribunal peut fixer une hausse plus forte, jusqu'à 50 % "
     "(article 35).", [f'{RENT}/art_32', f'{RENT}/art_33', f'{RENT}/art_35'], True),
    (f'{RENT}/art_45', 'ar', 'salma', '',
     'لا يُنهي المكري عقد الكراء إلا بإشعار بالإفراغ يوجهه إلى المكتري، مبني على سبب جدي ومشروع، من قبيل: أن يسترجع '
     'المحل ليسكنه هو أو زوجه أو أصوله أو فروعه المباشرون من الدرجة الأولى (ومن تذكرهم المادة)، أو ضرورة هدم المحل أو '
     'إصلاحه إصلاحا يستوجب الإفراغ، أو التماطل في أداء الكراء.', [], True),
    (f'{RENT}/art_45', 'darija', 'karim', '',
     'باش يخرجك، خاص مول الدار يصيفط ليك إشعار بالإفراغ فيه سبب جدي ومشروع، بحال: يرجع يسكن فيها هو ولا عائلتو القريبة، '
     'ولا خاصها تتهدم ولا إصلاحات ضرورية ما تدارش وانت ساكن، ولا كتعطّل فالخلاص.', [], False),
    ('/ma/loi/70-03/art_49', 'ar', 'salma', '',
     'لكل واحد من الزوجين أمواله الخاصة، منفصلة عن أموال الآخر. ويمكنهما أن يتفقا، في وثيقة مستقلة عن عقد الزواج، على '
     'كيفية تدبير الأموال التي سيكتسبانها أثناء الزواج واستثمارها وتوزيعها، وعلى العدلين إخبارهما بذلك عند الزواج. وإذا '
     'لم يكن بينهما اتفاق، يُرجع إلى القواعد العامة للإثبات، مع مراعاة عمل كل واحد منهما وما قدمه من مجهودات وما تحمله من '
     'أعباء لتنمية أموال الأسرة.', [], True),
    ('/ma/decret/2-25-983', 'ar', 'hamid', 'الحد الأدنى للأجر: 17,92 درهما للساعة خارج الفلاحة منذ فاتح يناير 2026',
     'حدد هذا المرسوم الحد الأدنى القانوني للأجر في 17,92 درهما عن كل ساعة شغل في الأنشطة غير الفلاحية ابتداء من فاتح '
     'يناير 2026، وفي 97,44 درهما عن كل يوم شغل في الأنشطة الفلاحية ابتداء من فاتح أبريل 2026، ونسخ المرسوم السابق رقم '
     '2.24.1122.', [], True),
    ('/ma/loi/41-26', 'ar', 'hamid',
     'فقدت أسرتك الدعم المباشر لأن أحد الزوجين أو ربّ الأسرة صُرّح به في الضمان الاجتماعي؟ منحة استثنائية لمدة 12 شهرا',
     'أضاف هذا القانون إلى قانون الدعم الاجتماعي المباشر منحة استثنائية للأسرة التي كانت تستفيد من الدعم ثم فقدته بسبب '
     'التصريح بأحد الزوجين أو برب الأسرة في نظام الضمان الاجتماعي للقطاع الخاص. تعادل المنحة مبلغ الدعم الذي كان من '
     'الممكن أن تستفيد منه الأسرة، وتُمنح مرة واحدة، وحدد المرسوم 2.26.434 مدتها في 12 شهرا متصلة أو متفرقة. وإذا فقد '
     'أحد الزوجين أو رب الأسرة عمله، يمكن للأسرة أن تستفيد من الدعم من جديد.', ['/ma/decret/2-26-434'], True),
    ('/words/rent', 'ar', 'salma', '', 'الوجيبة الكرائية هي مبلغ الكراء الذي يؤديه المكتري للمكري مقابل الانتفاع بالمحل.',
     [], True),
    ('/words/eviction', 'ar', 'salma', '',
     'الإفراغ هو خروج المكتري من المحل المكترى. لا يكون إلا للأسباب وبالإجراءات التي يحددها القانون، كالإشعار بالإفراغ.',
     [f'{RENT}/art_45'], True),
    ('/words/minimum-wage', 'ar', 'hamid', '',
     'الحد الأدنى للأجر (السميك) هو أقل أجر يحق للأجير أن يتقاضاه قانونا. يحدده مرسوم: عن كل ساعة في الأنشطة غير '
     'الفلاحية، وعن كل يوم في الأنشطة الفلاحية.', ['/ma/decret/2-25-983'], True),
    # Two of the weekly digest's headlines (R13): what the decision and the law say, nothing more.
    ('/ma/decision/2026/3-44-26', 'ar', 'hamid', 'مباراة المدرسة الوطنية للإدارة 2027: 50 مقعدا، والترشيح قبل 12 نوفمبر 2026',
     'تُجرى مباراة ولوج سلك التكوين الأساسي للمدرسة الوطنية للإدارة برسم سنة 2027 ابتداء من يوم السبت 30 يناير 2027 في '
     'الثامنة صباحا، على 50 مقعدا. يجب أن تصل ملفات الترشيح إلى المدرسة بالرباط، وأن يُسجَّل الترشيح إلكترونيا على '
     'بوابتها، في أجل لا يتجاوز يوم الخميس 12 نوفمبر 2026 في الرابعة بعد الزوال.', [], True),
    ('/ma/loi/32-26', 'ar', 'hamid', 'حراس شركات الحراسة: تتميم المادة 193 من مدونة الشغل',
     'أضاف هذا القانون إلى المادة 193 من مدونة الشغل أن الحراس الذين تذكرهم هي غير الذين تربطهم عقود شغل بمقاولات '
     'الحراسة. يُعمل به من تاريخ نشره، ولمقاولات الحراسة أجل أقصاه تسعة أشهر لتطبيقه على عقود الشغل الناشئة عن عقود '
     'أبرمتها قبل ذلك.', [], True),
]


class Command(BaseCommand):
    help = 'Seed demo explanations (dev only), after seed_demo_talk.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo data goes in a dev database only.')
        people = {u.username.removeprefix('demo-'): u for u in User.objects.filter(username__startswith='demo-')}
        if 'staff' not in people:
            raise CommandError('Run seed_demo_talk first: it makes the demo-* people.')
        Explanation.objects.filter(path__in={p for p, *_ in ITEMS}).delete()
        made = 0
        for path, register, who, headline, body, sources, checked in ITEMS:
            explanations.save(people[who], path, register, body, headline=headline, sources=sources,
                              note='أول صيغة' if register == 'ar' else '', consent=True)
            # What staff wrote checked itself; anyone else's waits for staff.
            if checked and Explanation.objects.filter(path=path, register=register, pending__isnull=False).exists():
                explanations.check(people['staff'], path, register)
            made += 1
        self.stdout.write(f'seeded {made} explanations ({sum(1 for *_, c in ITEMS if c)} checked)')
