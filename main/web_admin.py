import os
import json
from flask import Flask, render_template_string, request, session, redirect, url_for
from datetime import datetime
from collections import defaultdict
from i18n import I18N
from functools import wraps

app = Flask(__name__)
app.secret_key = 'cocoa_secret_key'  # セッション用

LOGFILE = 'preset_change_history.jsonl'
USER_LOG = 'user_action_log.jsonl'

LANG_SWITCHER_HTML = '''<form method="get" style="display:inline">
<select name="lang" onchange="this.form.submit()">
  <option value="en" {en}>English</option>
  <option value="ja" {ja}>日本語</option>
</select></form>'''

def get_lang():
    lang = request.args.get('lang') or session.get('lang')
    if lang:
        session['lang'] = lang
        return lang
    return I18N().detect_language()

def with_lang(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        lang = get_lang()
        i18n = I18N(lang)
        return f(i18n, *args, **kwargs)
    return wrapper

TEMPLATE = '''
<html><head><title>{{i18n.t('title')}}</title></head>
<body style="font-family:sans-serif;">
<h2>{{i18n.t('title')}}</h2>
<div style="float:right">''' + LANG_SWITCHER_HTML + '''</div>
<p>{{i18n.t('user')}}: <b>{{user}}</b> | <a href="/logout?lang={{lang}}">{{i18n.t('logout')}}</a></p>
<ul>
  <li><a href="/history?lang={{lang}}">{{i18n.t('history')}}</a></li>
  <li><a href="/userlog?lang={{lang}}">{{i18n.t('userlog')}}</a></li>
</ul>
<hr>
{% block content %}{% endblock %}
</body></html>
'''

def require_login(f):
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
@with_lang
def login(i18n):
    lang = get_lang()
    switcher = LANG_SWITCHER_HTML.format(en='selected' if lang=='en' else '', ja='selected' if lang=='ja' else '')
    if request.method == 'POST':
        user = request.form.get('user')
        if user:
            session['user'] = user
            log_user_action(user, 'login')
            return redirect(url_for('index', lang=lang))
    return f'''<form method="post">
        <input name="user" placeholder="{i18n.t('user')}">
        <button type="submit">{i18n.t('login') if i18n.t('login') != 'login' else 'ログイン'}</button>
    </form>'''

@app.route('/logout')
@with_lang
def logout(i18n):
    user = session.pop('user', None)
    lang = get_lang()
    if user:
        log_user_action(user, 'logout')
    return redirect(url_for('index', lang=lang))

@app.route('/')
@with_lang
def index(i18n):
    user = session.get('user', 'guest')
    lang = get_lang()
    switcher = LANG_SWITCHER_HTML.format(en='selected' if lang=='en' else '', ja='selected' if lang=='ja' else '')
    return render_template_string(TEMPLATE, user=user, i18n=i18n, lang=lang, switcher=switcher)

@app.route('/history')
@with_lang
def history(i18n):
    user = session.get('user', 'guest')
    lang = get_lang()
    switcher = LANG_SWITCHER_HTML.format(en='selected' if lang=='en' else '', ja='selected' if lang=='ja' else '')
    hist = []
    if os.path.exists(LOGFILE):
        with open(LOGFILE, encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                ev = json.loads(line)
                ts = datetime.fromtimestamp(ev['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                hist.append({'ts': ts, 'preset': ev['preset'], 'type': ev['type'], 'note': ev.get('note','')})
    content = f'<h3>{i18n.t("history")}</h3><table border=1 cellpadding=4><tr>' \
        f'<th>{i18n.t("time")}</th><th>{i18n.t("preset")}</th><th>{i18n.t("type")}</th><th>{i18n.t("note")}</th></tr>'
    for h in hist[-100:]:
        content += f"<tr><td>{h['ts']}</td><td>{h['preset']}</td><td>{h['type']}</td><td>{h['note']}</td></tr>"
    content += '</table>'
    return render_template_string(TEMPLATE + '{% block content %}' + content + '{% endblock %}', user=user, i18n=i18n, lang=lang, switcher=switcher)

@app.route('/userlog')
@with_lang
def userlog(i18n):
    user = session.get('user', 'guest')
    lang = get_lang()
    switcher = LANG_SWITCHER_HTML.format(en='selected' if lang=='en' else '', ja='selected' if lang=='ja' else '')
    logs = []
    if os.path.exists(USER_LOG):
        with open(USER_LOG, encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                ev = json.loads(line)
                ts = datetime.fromtimestamp(ev['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                logs.append({'ts': ts, 'user': ev['user'], 'operation': ev['operation']})
    content = f'<h3>{i18n.t("userlog")}</h3><table border=1 cellpadding=4><tr>' \
        f'<th>{i18n.t("time")}</th><th>{i18n.t("user")}</th><th>{i18n.t("operation")}</th></tr>'
    for l in logs[-100:]:
        content += f"<tr><td>{l['ts']}</td><td>{l['user']}</td><td>{l['operation']}</td></tr>"
    content += '</table>'
    return render_template_string(TEMPLATE + '{% block content %}' + content + '{% endblock %}', user=user, i18n=i18n, lang=lang, switcher=switcher)

def log_user_action(user, action):
    entry = {'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'user': user, 'action': action}
    with open(USER_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    app.run(debug=True, port=5004)
