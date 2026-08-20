import os, io, json, zipfile, requests, re
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# ═══ حالة المشروع ═══
state = {
    'files': {},
    'project_name': '',
    'settings': {
        'google_key': '',
        'google_model': '',
        'deepseek_key': '',
        'deepseek_model': '',
        'qwen_key': '',
        'qwen_model': '',
        'active_provider': 'deepseek'
    },
    'chat_history': []
}

# ═══════════════════════════════
#  PAGES
# ═══════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

# ═══════════════════════════════
#  SETTINGS
# ═══════════════════════════════

@app.route('/api/settings', methods=['POST'])
def save_settings():
    d = request.json
    state['settings'].update(d)
    return jsonify({'status': 'ok', 'msg': 'تم الحفظ'})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    s = state['settings'].copy()
    # إخفاء المفاتيح
    for k in ['google_key','deepseek_key','qwen_key']:
        if s.get(k):
            s[k] = s[k][:8] + '****'
    return jsonify(s)

# ═══════════════════════════════
#  UPLOAD ZIP
# ═══════════════════════════════

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'مفيش ملف'}), 400
    f = request.files['file']
    if not f.filename.endswith('.zip'):
        return jsonify({'error': 'لازم ZIP'}), 400

    state['project_name'] = f.filename.replace('.zip','')
    state['files'] = {}

    buf = io.BytesIO(f.read())
    with zipfile.ZipFile(buf, 'r') as z:
        for info in z.infolist():
            if info.is_dir() or info.file_size > 1_000_000:
                continue
            ext = os.path.splitext(info.filename)[1].lower()
            if ext in ['.png','.jpg','.jpeg','.gif','.ico','.woff',
                       '.ttf','.mp4','.mp3','.pdf','.exe','.dll',
                       '.pyc','.class','.jar','.so','.eot','.zip']:
                continue
            try:
                txt = z.read(info.filename).decode('utf-8', errors='replace')
                state['files'][info.filename] = txt
            except:
                pass

    return jsonify({
        'status': 'ok',
        'name': state['project_name'],
        'count': len(state['files']),
        'files': list(state['files'].keys())
    })

# ═══════════════════════════════
#  FILES CRUD
# ═══════════════════════════════

@app.route('/api/files')
def list_files():
    return jsonify({'files': list(state['files'].keys()),
                    'total': len(state['files'])})

@app.route('/api/file/<path:fp>', methods=['GET'])
def read_file(fp):
    if fp in state['files']:
        return jsonify({'path': fp, 'content': state['files'][fp]})
    return jsonify({'error': 'مش موجود'}), 404

@app.route('/api/file/<path:fp>', methods=['PUT'])
def write_file(fp):
    state['files'][fp] = request.json.get('content','')
    return jsonify({'status': 'ok'})

@app.route('/api/file/<path:fp>', methods=['DELETE'])
def del_file(fp):
    state['files'].pop(fp, None)
    return jsonify({'status': 'ok'})

@app.route('/api/file/new', methods=['POST'])
def new_file():
    d = request.json
    state['files'][d['path']] = d.get('content','')
    return jsonify({'status': 'ok'})

# ═══════════════════════════════
#  AI CHAT
# ═══════════════════════════════

@app.route('/api/chat', methods=['POST'])
def chat():
    d = request.json
    msg = d.get('message','')
    target = d.get('target_file', None)
    mode = d.get('mode', 'edit')

    # بناء السياق
    ctx = ""
    if target and target in state['files']:
        ctx = f"FILE: {target}\n```\n{state['files'][target]}\n```\n"
    elif target == '__ALL__':
        for fp, c in list(state['files'].items())[:40]:
            ctx += f"\n--- {fp} ---\n{c[:2000]}\n"

    sys_prompt = "أنت مطور خبير. عدّل وأرجع الملف الكامل داخل ```blocks```. اشرح بالعربي."
    if mode == 'rewrite':
        sys_prompt = "أعد كتابة الملف من الصفر. أرجع الملف الكامل داخل ```blocks```"

    messages = [{"role":"system","content":sys_prompt}]
    messages += state['chat_history'][-8:]
    user_content = f"{ctx}\nالتعليمات: {msg}" if ctx else msg
    messages.append({"role":"user","content":user_content})

    try:
        reply = call_ai(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    state['chat_history'].append({'role':'user','content':msg})
    state['chat_history'].append({'role':'assistant','content':reply})

    applied = []
    blocks = re.findall(r'```(?:\w+)?\n(.*?)```', reply, re.DOTALL)
    if target and target != '__ALL__' and blocks:
        state['files'][target] = blocks[0].strip()
        applied.append(target)

    return jsonify({'status':'ok','response':reply,'applied':applied})

@app.route('/api/chat/bulk', methods=['POST'])
def bulk():
    d = request.json
    instruction = d.get('instruction','')

    all_ctx = ""
    for fp, c in state['files'].items():
        all_ctx += f"\n{'='*50}\nFILE: {fp}\n{'='*50}\n{c[:3000]}\n"

    messages = [
        {"role":"system","content":
         f"أنت مهندس برمجيات. عدّل المشروع حسب التعليمات.\n"
         f"أرجع JSON:\n"
         f'{{"files":[{{"path":"...","action":"rewrite|edit|create|delete","content":"..."}}],'
         f'"explanation":"..."}}'},
        {"role":"user","content":f"الملفات:\n{all_ctx}\n\nالتعليمات: {instruction}"}
    ]

    try:
        reply = call_ai(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    applied = []
    try:
        jm = re.search(r'\{[\s\S]*\}', reply)
        if jm:
            data = json.loads(jm.group())
            for fc in data.get('files',[]):
                p = fc.get('path','')
                a = fc.get('action','edit')
                c = fc.get('content','')
                if a == 'delete':
                    state['files'].pop(p, None)
                elif c:
                    state['files'][p] = c
                applied.append(p)
    except:
        pass

    return jsonify({'status':'ok','response':reply,'applied':applied})

# ═══════════════════════════════
#  EXPORT ZIP
# ═══════════════════════════════

@app.route('/api/export', methods=['POST'])
def export():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for fp, c in state['files'].items():
            z.writestr(fp, c)
    buf.seek(0)
    name = state.get('project_name','project')
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f"{name}_modified.zip")

@app.route('/api/reset', methods=['POST'])
def reset():
    state['files'] = {}
    state['chat_history'] = []
    state['project_name'] = ''
    return jsonify({'status':'ok'})

# ═══════════════════════════════
#  AI CALL - 3 PROVIDERS
# ═══════════════════════════════

def call_ai(messages):
    s = state['settings']
    provider = s.get('active_provider', 'deepseek')

    # ─── GOOGLE ───
    if provider == 'google':
        key = s.get('google_key','')
        model = s.get('google_model','gemini-2.0-flash')
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={key}")
        contents = []
        for m in messages:
            role = 'user' if m['role'] in ('user','system') else 'model'
            contents.append({"role": role, "parts": [{"text": m['content']}]})
        r = requests.post(url, json={"contents": contents}, timeout=120)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']

    # ─── DEEPSEEK / QWEN (OpenAI compatible) ───
    if provider == 'deepseek':
        key = s.get('deepseek_key','')
        model = s.get('deepseek_model','deepseek-chat')
        url = "https://api.deepseek.com/v1/chat/completions"
    else:  # qwen
        key = s.get('qwen_key','')
        model = s.get('qwen_model','qwen-max')
        url = ("https://dashscope.aliyuncs.com/compatible-mode/"
               "v1/chat/completions")

    headers = {'Authorization': f'Bearer {key}',
               'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': messages,
               'max_tokens': 8192, 'temperature': 0.3}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']

# ═══════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
