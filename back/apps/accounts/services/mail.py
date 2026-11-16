"""The letters the site sends, in the account's language: a code, a link, nothing to track (no picture, no counted click).

Each letter goes as plain text with the same words as HTML beside it, so an Arabic letter reads right to left in every
mail program (some ignore a direction mark on the subject, so it is wrapped in an embedding). It comes
from «قانون المغرب» or SITE_NAME by the account's language, at DEFAULT_FROM_EMAIL's address (Resend in production: settings).

A letter that cannot go is written to the log and answered False; it never fails the request that sent it.

Every letter about the discussion carries a link that stops letters without signing in (R3): one discussion's, or all of
them, and the List-Unsubscribe headers mail providers read for their own one-click button. The account's own letters (a
code, a reset link, a new password or address) carry none: they are not a list.

The letters of access on request (apps.opendata: a request received, more asked, accepted, declined; a change
accepted; an access changed, renewed, ending in 30 days, ended; a key the staff ended) are the account's own too. Their words that depend on the language (what was granted, why) are in
ACCESS_WORDS; the services pick them with `language(user)`.

A letter to the people who run the site (`plain`: the Monday letter of the counts, apps.analytics; a request for access
arrived or answered) is plain text in English, from SITE_NAME, to the addresses a setting names; it goes, or is logged,
the same way."""
import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from email.utils import parseaddr
from urllib.parse import urlparse
from html import escape

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.signing import BadSignature, TimestampSigner
from django.utils import timezone

from apps.accounts.services.addresses import inbox, mail_blocked

log = logging.getLogger('accounts.mail')

_stops = TimestampSigner(salt='letters.stop')
STOP_MAX_AGE = 60 * 60 * 24 * 365
# The account's own letters: no stop link, no List-Unsubscribe.
ACCOUNT = {'code', 'reset', 'password_changed', 'email_changed', 'access_received', 'access_more', 'access_accepted',
           'access_declined', 'access_ending', 'access_ended', 'access_change_accepted', 'access_changed',
           'access_renewed', 'access_key_ended'}

LETTERS = {
    'code': {
        'ar': ('رمز تأكيد بريدك في «قانون المغرب»: {code}',
               'رمز تأكيد بريدك الإلكتروني في «قانون المغرب» هو:\n\n{code}\n\nيصلح هذا الرمز {minutes} دقيقة. '
               'إن لم تطلبه، فتجاهل هذه الرسالة.\n\nتدخل إلى حسابك باسم المستخدم {username} أو بهذا البريد.'),
        'fr': ('Votre code {site_name} : {code}',
               'Le code qui confirme votre adresse sur {site_name} est :\n\n{code}\n\nIl est valable {minutes} minutes. '
               'Si vous ne l’avez pas demandé, ignorez ce message.\n\n'
               'Vous vous connectez avec le nom d’utilisateur {username} ou avec cette adresse.'),
    },
    'reset': {
        'ar': ('كلمة سر جديدة لحسابك في «قانون المغرب»',
               'طُلبت كلمة سر جديدة لحسابك {username} في «قانون المغرب». افتح هذا الرابط واختر كلمة السر الجديدة:\n\n{link}\n\n'
               'يصلح الرابط {hours} ساعات، ومرة واحدة. إن لم تطلبه، فتجاهل هذه الرسالة: كلمة سرك لم تتبدل.'),
        'fr': ('Un nouveau mot de passe pour votre compte {site_name}',
               'Un nouveau mot de passe a été demandé pour votre compte {username} sur {site_name}. Ouvrez ce lien et '
               'choisissez-le :\n\n{link}\n\nLe lien est valable {hours} heures, une seule fois. Si vous ne l’avez '
               'pas demandé, ignorez ce message : votre mot de passe n’a pas changé.'),
    },
    'password_changed': {
        'ar': ('تبدّلت كلمة سر حسابك في «قانون المغرب»',
               'تبدّلت كلمة سر حسابك {username} في «قانون المغرب» يوم {when}، وخرجت أجهزتك الأخرى من الحساب.\n\n'
               'إن لم تكن أنت من بدّلها، فاطلب كلمة سر جديدة من هنا:\n\n{forgot}'),
        'fr': ('Le mot de passe de votre compte {site_name} a changé',
               'Le mot de passe de votre compte {username} sur {site_name} a changé le {when} ; vos autres appareils ont été '
               'déconnectés.\n\nSi ce n’est pas vous, demandez un nouveau mot de passe ici :\n\n{forgot}'),
    },
    'email_changed': {
        'ar': ('تبدّل بريد حسابك في «قانون المغرب»',
               'صار بريد حسابك {username} في «قانون المغرب» هو {new} منذ {when}. لن تصلك رسائلنا على هذا البريد بعد الآن.\n\n'
               'إن لم تكن أنت من بدّله، فقد عرف أحدهم كلمة سرك.{contact}'),
        'fr': ('L’adresse de votre compte {site_name} a changé',
               'Depuis le {when}, l’adresse de votre compte {username} sur {site_name} est {new}. Nos messages n’arriveront '
               'plus ici.\n\nSi ce n’est pas vous, quelqu’un connaît votre mot de passe.{contact}'),
    },
    'answer': {
        'ar': ('ردّ جديد على مساهمتك في «قانون المغرب»',
               'كتب أحدهم ردا على مساهمتك حول {label}:\n\n{link}\n\n'
               'لإيقاف هذه الرسائل: {settings}'),
        'fr': ('Une réponse à votre contribution sur {site_name}',
               'Quelqu’un a répondu à votre contribution sur {label} :\n\n{link}\n\n'
               'Pour ne plus recevoir ces messages : {settings}'),
    },
    'new': {
        'ar': ('جديد في نقاش تتابعه في «قانون المغرب»',
               'كُتبت مساهمة جديدة في النقاش حول {label}:\n\n{link}\n\n'
               'لإيقاف هذه الرسائل: {settings}'),
        'fr': ('Du nouveau dans une discussion que vous suivez',
               'Une nouvelle contribution a été écrite sur {label} :\n\n{link}\n\n'
               'Pour ne plus recevoir ces messages : {settings}'),
    },
    'removed': {
        'ar': ('أُزيلت إحدى مساهماتك في «قانون المغرب»',
               'أزال المراجعون مساهمتك حول {label} لأنها تخالف القاعدة {rule} من قواعد النقاش.\n'
               'يمكنك الاعتراض مرة واحدة من صفحة حسابك: {settings}'),
        'fr': ('Une de vos contributions a été retirée',
               'Les relecteurs ont retiré votre contribution sur {label} : elle enfreint la règle {rule} des règles '
               'de discussion.\nVous pouvez faire appel une fois depuis votre compte : {settings}'),
    },
    'approved': {
        'ar': ('نُشرت مساهمتك في «قانون المغرب»',
               'راجع أحد المراجعين مساهمتك حول {label} ونشرها. يقرؤها الناس الآن:\n\n{link}'),
        'fr': ('Votre contribution est publiée sur {site_name}',
               'Un relecteur a publié votre contribution sur {label}. Elle est désormais lisible :\n\n{link}'),
    },
    'sent_back': {
        'ar': ('مساهمتك تحتاج تعديلا قبل نشرها',
               'أعاد أحد المراجعين مساهمتك حول {label} لتعدّلها:\n\n«{note}»\n\n'
               'عدّلها من هنا، وتعود إلى المراجعة: {link}'),
        'fr': ('Votre contribution est à corriger avant publication',
               'Un relecteur vous renvoie votre contribution sur {label} :\n\n« {note} »\n\n'
               'Corrigez-la ici ; elle repartira en relecture : {link}'),
    },
    'redacted': {
        'ar': ('حذفنا جزءا من مساهمتك',
               'حذف أحد المراجعين من مساهمتك حول {label} ما يخالف قواعد النقاش (رقم أو اسم أو جزء من صورة)، '
               'ونشر الباقي: {link}'),
        'fr': ('Nous avons retiré une partie de votre contribution',
               'Un relecteur a retiré de votre contribution sur {label} ce qui enfreignait les règles (un numéro, un '
               'nom ou une partie d\u2019image) et publié le reste : {link}'),
    },
    'follows': {
        'ar': ('تبدّل ما تتابعه في «قانون المغرب»',
               'منذ رسالتنا الأخيرة، تبدّل ما تتابعه:\n\n{lines}\n\nكل ما تتابعه: {follows}'),
        'fr': ('Du changement dans ce que vous suivez sur {site_name}',
               'Depuis notre dernier message, ce que vous suivez a changé :\n\n{lines}\n\nTout ce que vous suivez : '
               '{follows}'),
    },
    'digest': {
        'ar': ('مساهمات تنتظر مراجعتك في «قانون المغرب»',
               '{count} مساهمة تنتظر في صفحة المراجعة، بعضها منذ أكثر من 12 ساعة:\n\n{link}'),
        'fr': ('Des contributions attendent votre relecture',
               '{count} contributions attendent dans la page de relecture, certaines depuis plus de 12 heures :\n\n'
               '{link}'),
    },
    'access_received': {
        'ar': ('وصل طلبك للوصول إلى بيانات «قانون المغرب»',
               'وصلنا طلبك باسم «{name}» للوصول إلى {granted}. نجيبك في أجل {days} أيام عمل، برسالة إلى هذا البريد.\n\n'
               'تجد طلبك وما صار إليه في صفحة وصولك: {account}'),
        'fr': ('Votre demande d’accès à {site_name} est reçue',
               'Nous avons reçu votre demande au nom de « {name} », pour {granted}. Nous vous répondrons sous {days} '
               'jours ouvrables, par un message à cette adresse.\n\nVotre demande et sa suite, sur votre page d’accès : '
               '{account}'),
    },
    'access_more': {
        'ar': ('سؤال عن طلبك للوصول إلى بيانات «قانون المغرب»',
               'قرأنا طلبك باسم «{name}»، ونحتاج أن نعرف أكثر قبل أن نجيب:\n\n«{line}»\n\n'
               'أجب من صفحة وصولك، فيعود طلبك إلى مكانه في الانتظار: {account}'),
        'fr': ('Une question sur votre demande d’accès à {site_name}',
               'Nous avons lu votre demande au nom de « {name} » ; avant de répondre, nous avons besoin d’en savoir '
               'plus :\n\n« {line} »\n\nRépondez depuis votre page d’accès ; votre demande reprendra sa place : {account}'),
    },
    'access_accepted': {
        'ar': ('قُبل طلبك للوصول إلى بيانات «قانون المغرب»',
               'قبلنا طلبك باسم «{name}». صار لحسابك الوصول إلى {granted} حتى {ends_on}.\n\n'
               'الطلبات في الدقيقة: {minute}\nالطلبات في اليوم: {calls}\nالمواد في اليوم: {articles}\n\n'
               'اصنع مفتاحك من صفحة وصولك: {account}\n\nيظهر المفتاح مرة واحدة فقط، فاحفظه حيث لا يراه غيرك.'),
        'fr': ('Votre demande d’accès à {site_name} est acceptée',
               'Nous avons accepté votre demande au nom de « {name} ». Votre compte a accès à {granted} jusqu’au '
               '{ends_on}.\n\nRequêtes par minute : {minute}\nRequêtes par jour : {calls}\nArticles par jour : '
               '{articles}\n\nCréez votre clé depuis votre page d’accès : {account}\n\nElle ne s’affiche qu’une fois : '
               'gardez-la là où personne d’autre ne la voit.'),
    },
    'access_declined': {
        'ar': ('جواب طلبك للوصول إلى بيانات «قانون المغرب»',
               'قرأنا طلبك باسم «{name}»، ولم نقبله: {reason}\n\n'
               'يمكنك أن تطلب من جديد ابتداء من {again}، من صفحة وصولك: {account}'),
        'fr': ('La réponse à votre demande d’accès à {site_name}',
               'Nous avons lu votre demande au nom de « {name} » et ne l’avons pas acceptée : {reason}\n\n'
               'Vous pourrez demander à nouveau à partir du {again}, depuis votre page d’accès : {account}'),
    },
    'access_ending': {
        'ar': ('ينتهي وصولك إلى بيانات «قانون المغرب» يوم {ends_on}',
               'ينتهي وصول حسابك إلى {granted} يوم {ends_on}، وتتوقف مفاتيحه معه.\n\n'
               'إن كنت ما زلت تحتاجه، فأرسل طلبا جديدا من صفحة وصولك بعد ذلك اليوم: {account}'),
        'fr': ('Votre accès à {site_name} prend fin le {ends_on}',
               'L’accès de votre compte à {granted} prend fin le {ends_on}, et ses clés avec lui.\n\n'
               'Si vous en avez encore besoin, envoyez une nouvelle demande depuis votre page d’accès après cette date : '
               '{account}'),
    },
    'access_ended': {
        'ar': ('انتهى وصولك إلى بيانات «قانون المغرب»',
               'انتهى وصول حسابك إلى {granted}: {reason}\n\n'
               'توقفت مفاتيحه، فلا تفتح شيئا بعد الآن. يمكنك أن ترسل طلبا جديدا من صفحة وصولك: {account}'),
        'fr': ('Votre accès à {site_name} a pris fin',
               'L’accès de votre compte à {granted} a pris fin : {reason}\n\n'
               'Ses clés n’ouvrent plus rien. Vous pouvez envoyer une nouvelle demande depuis votre page d’accès : '
               '{account}'),
    },
    # A request to change an access, accepted; the staff changing an access, renewing it, ending one of its keys. The
    # keys of a changed or renewed access keep working.
    'access_change_accepted': {
        'ar': ('قُبل طلبك لتعديل وصولك إلى بيانات «قانون المغرب»',
               'قبلنا طلبك باسم «{name}» لتعديل وصولك. صار لحسابك الوصول إلى {granted} حتى {ends_on}.\n\n'
               'الطلبات في الدقيقة: {minute}\nالطلبات في اليوم: {calls}\nالمواد في اليوم: {articles}\n\n'
               'مفاتيحك تبقى كما هي، وتسري عليها هذه الحدود من الآن. تجد وصولك في: {account}'),
        'fr': ('Votre demande de modifier votre accès à {site_name} est acceptée',
               'Nous avons accepté votre demande au nom de « {name} » de modifier votre accès. Votre compte a désormais '
               'accès à {granted} jusqu’au {ends_on}.\n\nRequêtes par minute : {minute}\nRequêtes par jour : {calls}\n'
               'Articles par jour : {articles}\n\nVos clés restent les mêmes ; ces limites s’y appliquent dès '
               'maintenant. Votre accès : {account}'),
    },
    'access_changed': {
        'ar': ('تبدّل وصولك إلى بيانات «قانون المغرب»',
               'بدّلنا وصول حسابك. صار له الوصول إلى {granted} حتى {ends_on}.\n\n'
               'الطلبات في الدقيقة: {minute}\nالطلبات في اليوم: {calls}\nالمواد في اليوم: {articles}\n\n'
               'مفاتيحك تبقى كما هي، وتسري عليها هذه الحدود من الآن. تجد وصولك في: {account}'),
        'fr': ('Votre accès à {site_name} a changé',
               'Nous avons modifié l’accès de votre compte. Il a désormais accès à {granted} jusqu’au {ends_on}.\n\n'
               'Requêtes par minute : {minute}\nRequêtes par jour : {calls}\nArticles par jour : {articles}\n\n'
               'Vos clés restent les mêmes ; ces limites s’y appliquent dès maintenant. Votre accès : {account}'),
    },
    'access_renewed': {
        'ar': ('تجدّد وصولك إلى بيانات «قانون المغرب» حتى {ends_on}',
               'جدّدنا وصول حسابك إلى {granted}، فصار ينتهي يوم {ends_on}. مفاتيحك تبقى كما هي.\n\n'
               'تجد وصولك في: {account}'),
        'fr': ('Votre accès à {site_name} est renouvelé jusqu’au {ends_on}',
               'Nous avons renouvelé l’accès de votre compte à {granted} : il prend fin le {ends_on}. Vos clés restent '
               'les mêmes.\n\nVotre accès : {account}'),
    },
    'access_key_ended': {
        'ar': ('أوقفنا أحد مفاتيح وصولك إلى بيانات «قانون المغرب»',
               'أوقفنا مفتاحك «{key}» الذي يبدأ بـ {prefix}، لأنه قد يكون ظهر حيث يقرؤه غيرك. لا يفتح شيئا بعد الآن، '
               'ووصولك نفسه باق.\n\nاصنع مفتاحا جديدا من صفحة وصولك، واحفظه حيث لا يراه غيرك: {account}'),
        'fr': ('Nous avons arrêté une clé de votre accès à {site_name}',
               'Nous avons arrêté votre clé « {key} », qui commence par {prefix} : elle a pu apparaître là où d’autres '
               'peuvent la lire. Elle n’ouvre plus rien ; votre accès, lui, reste ouvert.\n\nCréez une nouvelle clé '
               'depuis votre page d’accès et gardez-la là où personne d’autre ne la voit : {account}'),
    },
}

# The access letters' words that depend on the language, by the codes of apps.opendata.models: what was asked or
# granted (`granted`), a key its holder gave no name (`unnamed`), why a request was declined (`declined`,
# Request.Reason), why an access ended (`ended`, Access.Ended; the account's deletion sends no letter).
ACCESS_WORDS = {
    'ar': {
        'granted': {'api': 'الواجهة البرمجية (API)', 'data': 'قاعدة البيانات',
                    'both': 'الواجهة البرمجية (API) وقاعدة البيانات'},
        'unnamed': 'بلا اسم',
        'declined': {'unclear': 'لم يتضح لنا ما ستصنعه بالبيانات. قل لنا أكثر في طلبك القادم.',
                     'identity': 'لم نستطع أن نعرف من يطلب.',
                     'scope': 'المطلوب أكثر مما يحتاجه الاستعمال الذي وصفته.',
                     'terms': 'الاستعمال الذي وصفته يخالف شروط الوصول.',
                     'later': 'لا نعطي وصولا جديدا في هذا الوقت.'},
        'ended': {'asked': 'أُنهي بطلب منك.',
                  'terms': 'استُعمل بما يخالف شروط الوصول.',
                  'leaked': 'ظهر أحد مفاتيحه حيث يقرؤه غيرك.',
                  'unused': 'لم يُستعمل منذ مدة.',
                  'expired': 'حلّ تاريخ انتهائه.'},
    },
    'fr': {
        'granted': {'api': 'l’API', 'data': 'la base de données', 'both': 'l’API et la base de données'},
        'unnamed': 'sans nom',
        'declined': {'unclear': 'nous ne voyons pas assez ce que vous ferez des données ; dites-en plus dans votre '
                                'prochaine demande.',
                     'identity': 'nous ne pouvons pas savoir qui demande.',
                     'scope': 'vous demandez plus que l’usage décrit n’en a besoin.',
                     'terms': 'l’usage décrit enfreint les conditions d’accès.',
                     'later': 'nous n’ouvrons pas de nouvel accès pour le moment.'},
        'ended': {'asked': 'vous l’avez demandé.',
                  'terms': 'il a été utilisé contre les conditions d’accès.',
                  'leaked': 'une de ses clés est apparue là où d’autres peuvent la lire.',
                  'unused': 'il n’était plus utilisé.',
                  'expired': 'sa date de fin est passée.'},
    },
}

STOP_LINE = {'ar': '\n\nلإيقاف رسائل هذا النقاش أو كل الرسائل: {stop}',
             'fr': '\n\nPour ne plus recevoir les messages de cette discussion, ou plus aucun : {stop}'}


def stop_token(user, path: str = '') -> str:
    return _stops.sign(f'{user.pk}|{path}')


def read_stop(token: str) -> tuple[int, str] | None:
    try:
        user_id, path = _stops.unsign(token or '', max_age=STOP_MAX_AGE).split('|', 1)
        return int(user_id), path
    except (BadSignature, ValueError):
        return None


CONTACT_LINE = {'ar': ' اكتب إلينا: {email}', 'fr': ' Écrivez-nous : {email}'}
_URL = re.compile(r'https?://[^\s<>"]+')
# Embedding marks for an Arabic subject (RLE … PDF): a direction mark alone is ignored by some mail programs.
RLE, PDF = '\u202b', '\u202c'


def from_name(lang: str) -> str:
    """Who a letter is from: «قانون المغرب» in Arabic (the name on the site's wordmark: «قانون» alone is the common
    word for «law», and names nobody in an inbox), the site's Latin name in French."""
    return 'قانون المغرب' if lang == 'ar' else settings.SITE_NAME


def signed(lang: str) -> str:
    """A letter's last line, the address people type: after «قانون المغرب» in Arabic, alone in French, where the site's name is
    the address's own word."""
    return site() if lang == 'fr' else f'{from_name(lang)} · {site()}'


def site() -> str:
    """The address people type, «3adala.com»: the name is said with it wherever a letter or a message signs (8 Nov
    2026: the address is 3adala.com, the name «قانون المغرب» / SITE_NAME, never the ministry's portal «عدالة»)."""
    return urlparse(settings.SITE_URL).netloc.removeprefix('www.') or settings.SITE_URL


def _head(lang: str) -> str:
    """A letter's head: who writes and the address people type, so a letter is known at a glance for the site's own.
    The name in Arabic with the address beside it; in French the address, which is the site's name there."""
    name = f'<strong style="font-size:19px;color:#4b3a9a">{escape(from_name(lang))}</strong>' if lang == 'ar' else ''
    address = (f'<a href="{settings.SITE_URL}" dir="ltr" style="color:#4b3a9a;text-decoration:none;'
               f'font-size:{"14px" if name else "19px;font-weight:700"}">{site()}</a>')
    return (f'<p style="margin:0 0 18px;padding:0 0 12px;border-bottom:1px solid #e4dccb">'
            f'{name}{" &nbsp;·&nbsp; " if name else ""}{address}</p>')


def _html(lang: str, title: str, body: str) -> str:
    """The same words as HTML: each paragraph finds its own direction, links are links, the code stands out."""
    direction = 'rtl' if lang == 'ar' else 'ltr'
    paragraphs = []
    for para in body.split('\n\n'):
        text = para.strip()
        if re.fullmatch(r'\d{6}', text):
            paragraphs.append('<p dir="ltr" style="margin:0 0 18px;font-size:30px;font-weight:700;letter-spacing:6px;'
                              f'text-align:center;color:#1f1a14">{text}</p>')
            continue
        html = _URL.sub(lambda m: f'<a href="{m.group(0)}" dir="ltr" style="color:#4b3a9a;word-break:break-all">'
                                  f'{m.group(0)}</a>', escape(text, quote=False)).replace('\n', '<br>')
        paragraphs.append(f'<p style="margin:0 0 14px;unicode-bidi:plaintext;line-height:1.7">{html}</p>')
    return (f'<!DOCTYPE html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title></head>'
            f'<body style="margin:0;padding:24px 12px;background:#f6f1e7">'
            f'<div dir="{direction}" style="max-width:520px;margin:0 auto;padding:28px 24px;background:#fffdf8;'
            f'border:1px solid #e4dccb;border-radius:8px;font-family:Tahoma,Arial,sans-serif;font-size:16px;'
            f'color:#2b251d;text-align:start">{_head(lang)}{"".join(paragraphs)}'
            f'<p style="margin:22px 0 0;font-size:13px;color:#7a705f">{signed(lang).removesuffix(site())}'
            f'<a href="{settings.SITE_URL}" dir="ltr" style="color:#7a705f">{site()}</a></p>'
            f'</div></body></html>')


def may_mail(user, kind: str) -> bool:
    """Claim this account's next `kind` letter (a reset link, a code) that anyone may make us send: one
    every ACCOUNT_MAIL_GAP_S and ACCOUNT_MAIL_PER_DAY a day. Past it the request is answered as if the
    letter went, and the one already sent still works. A cache that cannot be read lets it go."""
    try:
        if not cache.add(f'mail:{kind}:{user.pk}:gap', 1, timeout=settings.ACCOUNT_MAIL_GAP_S):
            return False
    except Exception:  # noqa: BLE001
        return True
    return _claim(f'mail:{kind}:{user.pk}:{timezone.localdate():%Y%m%d}', settings.ACCOUNT_MAIL_PER_DAY)


def _claim(key: str, most: int) -> bool:
    """One more of today's `most` under `key`. A cache that cannot be read lets it go."""
    try:
        cache.add(key, 0, timeout=26 * 3600)
        try:
            sent = cache.incr(key)
        except ValueError:  # expired between add and incr
            cache.set(key, 1, timeout=26 * 3600)
            sent = 1
    except Exception:  # noqa: BLE001
        return True
    return sent <= most


def may_reach(address: str, kind: str) -> bool:
    """Claim one of the day's ACCOUNT_MAIL_PER_ADDRESS letters of `kind` (a code, a reset link) to this inbox, whichever
    account asks: an account opened on someone else's address, or moved from address to address, cannot fill a
    stranger's inbox. The inbox is counted folded (addresses.inbox: a «+tag» or Gmail's dots make no new one) and under
    an HMAC, never as written."""
    digest = hmac.new(settings.SECRET_KEY.encode(), f'inbox\x1f{inbox(address)}'.encode(), hashlib.sha256).hexdigest()
    return _claim(f'mail:{kind}:to:{digest[:32]}:{timezone.localdate():%Y%m%d}', settings.ACCOUNT_MAIL_PER_ADDRESS)


def language(user) -> str:
    """The language the account's letters are written in."""
    return user.preferred_language if user.preferred_language in ('ar', 'fr') else 'ar'


@dataclass(frozen=True)
class Letter:
    """A letter as the account will read it: its language, its subject, and its words before the last line (the HTML
    part is made from them). `body` is the plain text whole, as it is sent."""
    language: str
    subject: str
    words: str
    headers: dict

    @property
    def body(self) -> str:
        return f'{self.words}\n\n{signed(self.language)}'


def compose(user, letter: str, path: str = '', **words) -> Letter:
    """One letter to the account, made and not sent: what `send` sends, and what the access desk shows before a decision
    (so what is shown cannot differ from what goes)."""
    lang = language(user)
    subject, body = LETTERS[letter][lang]
    words.setdefault('settings', f'{settings.SITE_URL}/account/settings')
    words.setdefault('username', user.username)
    words.setdefault('site_name', settings.SITE_NAME)
    words.setdefault('when', timezone.localtime().strftime('%d/%m/%Y %H:%M'))
    words.setdefault('forgot', f'{settings.SITE_URL}/forgot')
    words.setdefault('contact', CONTACT_LINE[lang].format(email=settings.CONTACT_EMAIL) if settings.CONTACT_EMAIL else '')
    headers = {}
    if letter not in ACCOUNT:
        token = stop_token(user, path)
        words['stop'] = f'{settings.SITE_URL}/letters/stop?t={token}'
        body += STOP_LINE[lang]
        headers = {'List-Unsubscribe': f'<{settings.SITE_URL}/api/discussion/letters/stop/?t={token}&scope=all>',
                   'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}
    return Letter(lang, subject.format(**words), body.format(**words), headers)


def send(user, letter: str, path: str = '', to: str | None = None, **words) -> bool:
    """One letter to the account (or to `to`, the address it is about to leave). True once the mail service took it."""
    address = to or user.email
    if not address or mail_blocked(address) or address.endswith('.invalid'):
        return False
    made = compose(user, letter, path, **words)
    lang, subject = made.language, made.subject
    message = EmailMultiAlternatives(
        f'{RLE}{subject}{PDF}' if lang == 'ar' else subject, made.body,
        # As text: Resend's API takes the name in UTF-8 (an encoded word would be shown as is); SMTP encodes it itself.
        f'{from_name(lang)} <{parseaddr(settings.DEFAULT_FROM_EMAIL)[1]}>', [address], headers=made.headers,
        reply_to=[settings.CONTACT_EMAIL] if settings.CONTACT_EMAIL else None)
    message.attach_alternative(_html(lang, subject, made.words), 'text/html')
    try:
        message.send()
    except Exception:  # a letter that cannot go must not fail the request that sent it
        log.warning('letter %s to account %s not sent', letter, user.pk, exc_info=True)
        return False
    return True


def plain(to: list[str], subject: str, body: str) -> bool:
    """A plain-text letter to the people who run the site, from SITE_NAME at DEFAULT_FROM_EMAIL's address. True once the
    mail service took it; a letter that cannot go is logged (by its subject, never its addresses) and answered False."""
    message = EmailMessage(subject, body, f'{settings.SITE_NAME} <{parseaddr(settings.DEFAULT_FROM_EMAIL)[1]}>', to)
    try:
        message.send()
    except Exception:  # the caller says it was not sent; the log says why
        log.warning('letter «%s» not sent', subject, exc_info=True)
        return False
    return True
