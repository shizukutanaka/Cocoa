import json
import os
from flask import Flask, render_template_string, request
from preset_change_history import PresetChangeHistory
from datetime import datetime
from collections import Counter

app = Flask(__name__)

HIST = PresetChangeHistory()

TEMPLATE = '''
<html><head><title>プリセット履歴ダッシュボード</title></head>
<body style="font-family:sans-serif;">
<h2>プリセット履歴ダッシュボード</h2>
<form method="get">
  プリセット名: <input name="preset" value="{{preset}}">
  <input type="submit" value="履歴表示">
</form>
{% if entries %}
  <h3>{{preset}} の履歴 ({{entries|length}}件)</h3>
  <table border=1 cellpadding=4>
    <tr><th>時刻</th><th>種別</th><th>ユーザー</th><th>メモ</th></tr>
    {% for e in entries %}
    <tr>
      <td>{{e.timestamp|dt}}</td>
      <td>{{e.change_type}}</td>
      <td>{{e.user}}</td>
      <td>{{e.note}}</td>
    </tr>
    {% endfor %}
  </table>
  <h4>操作種別ごとの件数</h4>
  <ul>
    {% for k,v in stats.items() %}<li>{{k}}: {{v}}</li>{% endfor %}
  </ul>
{% endif %}
</body></html>
'''

def dt_filter(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

app.jinja_env.filters['dt'] = dt_filter

@app.route('/', methods=['GET'])
def dashboard():
    preset = request.args.get('preset', '')
    entries = list(HIST.iter_history(preset)) if preset else []
    stats = Counter(e['change_type'] for e in entries)
    return render_template_string(TEMPLATE, preset=preset, entries=entries, stats=stats)

if __name__ == '__main__':
    app.run(debug=True, port=5002)
