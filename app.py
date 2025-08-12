import os
import logging
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for, session, jsonify, send_file
from werkzeug.utils import secure_filename
import workorder_classification
import pandas as pd
import requests
import json
import time
import uuid
from collections import defaultdict
from tqdm import tqdm
import threading
import queue
import concurrent.futures

UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'your-secret-key-here'  # 请更改为随机字符串

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(RESULT_FOLDER):
    os.makedirs(RESULT_FOLDER)

# 存储任务状态
task_status = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 读取Excel文件
def read_excel(file_path):
    try:
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        print(f"读取Excel文件时出错: {e}")
        return None

# 按工单ID分组对话内容
def group_by_work_order(df):
    work_orders = defaultdict(list)
    
    # 确保数据按created_at排序
    df = df.sort_values(by=['work_order_id', 'created_at'])
    
    # 添加进度条
    for _, row in tqdm(df.iterrows(), total=len(df), desc="分组工单数据"):
        work_id = row['work_order_id']
        content = row['content']
        user_name = row['oa_user_name']
        
        # 跳过空内容或AI回复（oa_user_name为空）
        if pd.isna(content) or content.strip() == '' or pd.isna(user_name):
            continue
            
        work_orders[work_id].append({
            'user': user_name,
            'content': content
        })
    
    return work_orders

# 通用API调用函数
def call_dashscope_api(api_key, model, system_prompt, user_prompt, max_retries=3, timeout=90, enable_thinking=False):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if model.startswith('qwen3'):
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
        },
            "extra_body": {"enable_thinking": enable_thinking} if enable_thinking else {}
        }
    else:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "extra_body": {"enable_thinking": enable_thinking} if enable_thinking else {}
        }
    for retry in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            if model.startswith('qwen3'):
                if 'output' in result and 'text' in result['output']:
                    return result['output']['text'].strip()
            else:
                if 'choices' in result and len(result['choices']) > 0 and 'message' in result['choices'][0]:
                    return result['choices'][0]['message']['content'].strip()
        except requests.exceptions.Timeout:
            logging.warning(f"API请求超时，重试 {retry+1}/{max_retries}")
        except requests.exceptions.RequestException as e:
            logging.error(f"API调用出错: {e}")
        time.sleep(2 ** retry)  # 指数退避
    return None

# 调用百炼API整理对话
def format_conversations(api_key, conversations, task_id):
    formatted_texts = {}
    total_work_orders = len(conversations)
    processed_count = 0

    def process_conversation(work_id, messages):
        nonlocal processed_count
        conversation_text = "\n".join([f"{msg['user']}: {msg['content']}" for msg in messages])
        prompt = f"""以下是一段工单对话记录，其中说话者名称为oa_user_name。请分析并整理成易于分析的文本格式，区分用户和工作人员的角色（基于名称或内容上下文判断用户是提问者，工作人员是回答者），删除任何AI或系统回复，并格式化为：\nUser: [内容]\nStaff: [内容]\n...\n如果无法区分或没有有效内容，返回空字符串。\n\n对话内容：\n{conversation_text}\n\n请返回整理后的文本。"""
        system_prompt = "你是一个专业的对话整理助手，擅长从工单记录中区分角色并格式化文本。"
        formatted_text = call_dashscope_api(api_key, "qwen-plus", system_prompt, prompt)
        if formatted_text:
            formatted_texts[work_id] = formatted_text
        processed_count += 1
        progress = (processed_count / total_work_orders) * 100
        task_status[task_id]['progress'] = progress
        task_status[task_id]['status'] = f"正在格式化工单 {work_id} ({processed_count}/{total_work_orders})"

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_conversation, work_id, messages) for work_id, messages in conversations.items()]
        concurrent.futures.wait(futures)

    return formatted_texts

# 调用百炼API生成QA对
def generate_qa_pairs(api_key, formatted_texts, task_id):
    qa_pairs = []
    total_work_orders = len(formatted_texts)
    processed_count = 0

    def process_formatted_text(work_id, text):
        nonlocal processed_count
        prompt = f"""角色
你是一个从工单记录中提取问题和解决方案的助手。你的任务是从给定的工单记录中识别出问题（即用户遇到的困难或故障）和相应的解决方案（即为解决问题采取的措施或行动），并将它们整理成 QA 对。任务
请从以下工单记录中提取问题和解决方案，并以指定的格式输出。如果工单记录中包含多个问题或解决方案，请将每个 QA 对分别列出。
如果问题或解决方案没有明确说明，根据上下文进行推断。
如果无法推断，忽略即可。
请确保提取的信息准确无误，不要添加额外的内容或臆测。

注意事项  工单记录通常包含用户报告的问题、工程师的检查结果以及采取的解决方案。请着重从这些部分提取信息。
问题通常是用户遇到的故障或异常现象，解决方案则是为解决问题而采取的具体行动。
如果工单记录中包含多个独立的问题和解决方案，请为每个问题和其对应的解决方案生成一个 QA 对。


工单文本：
{text}

请提取问答对，格式如下：
{{
  "qa_pairs": [
    {{
      "question": "问题1",
      "answer": "回答1"
    }},
    ...
  ]
}}
"""
        system_prompt = "你是一个工单问答提取助手。你的任务是根据以下工单对话内容,理解并抽取出核心问题和对应的解决方案或回答。请确保提取的答案是完整且准确的,并且只包含与问题直接相关的信息。如果对话中没有明确的答案,请说明。请以JSON格式输出结果。如果存在多个问答对,请输出一个JSON数组。"
        response_text = call_dashscope_api(api_key, "qwen-max", system_prompt, prompt)
        if response_text:
            try:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                if json_start != -1 and json_end != -1:
                    json_str = response_text[json_start:json_end+1]
                    qa_data = json.loads(json_str)
                    if 'qa_pairs' in qa_data and len(qa_data['qa_pairs']) > 0:
                        for qa in qa_data['qa_pairs']:
                            qa_pairs.append({
                                'work_order_id': work_id,
                                'question': qa['question'],
                                'answer': qa['answer']
                            })
            except Exception as e:
                logging.error(f"解析工单 {work_id} 的JSON结果时出错: {e}")
        processed_count += 1
        progress = (processed_count / total_work_orders) * 100
        task_status[task_id]['progress'] = progress
        task_status[task_id]['status'] = f"正在处理工单 {work_id} ({processed_count}/{total_work_orders})"

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_formatted_text, work_id, text) for work_id, text in formatted_texts.items()]
        concurrent.futures.wait(futures)

    return qa_pairs

def clean_qa_pairs(api_key, qa_pairs, task_id):
    cleaned_qa = []
    total_pairs = len(qa_pairs)
    processed_count = 0

    def process_qa_pair(qa):
        nonlocal processed_count
        prompt = f"""目标： 指示LLM充当问答对的客观、专家评估员，判断其“真实性”（事实准确性、溯源性、无幻觉）和“有效性”（相关性、连贯性、实用性）。
角色分配： 提示开头明确定义LLM的角色和任务：
"您是一位资深的自然语言处理研究员和问答系统评估专家。您的任务是根据预定义的‘真实性’和‘有效性’标准，严格评估给定问答对（QA Pair）的质量。

有效且高质量问答对的评估标准：
评估类别:
真实性 (Realness):事实准确性，无幻觉，溯源性/忠实性  有效性：相关性，连贯性与清晰度，完整性与特异性，实用性与帮助性
事实准确性	答案是否基于通用知识或提供的上下文，在事实层面是正确的？	
无幻觉	答案是否包含编造信息、矛盾、或与问题/上下文无关的细节？	1: 存在严重幻觉（捏造、矛盾）。 
溯源性/忠实性 (如提供上下文)	如果提供了上下文，答案是否直接由该上下文支持，并忠实于其内容，没有引入外部或偏离的信息？	
相关性	答案是否直接、完整地回应了问题，并满足了用户的潜在信息需求？ 
连贯性与清晰度	答案是否结构良好、逻辑流畅、易于理解、语法正确且无歧义？
完整性与特异性	答案是否提供了足够详细的信息，既不冗长也不遗漏关键点？	
实用性与帮助性	答案是否对用户有用，提供可操作的见解或解决了实际问题？	

如果符合，返回'yes'，否则'no'。只返回'yes'或'no'。
问题: {qa['question']}
答案: {qa['answer']}"""
        system_prompt = "你是一个QA验证助手，使用推理模式评估QA对的真实性和相关性。"
        response = call_dashscope_api(api_key, "qwen-plus", system_prompt, prompt)
        if response and response.lower() == 'yes':
            cleaned_qa.append(qa)
        processed_count += 1
        progress = 50 + (processed_count / total_pairs) * 40  # 从50%到90%
        task_status[task_id]['progress'] = progress
        task_status[task_id]['status'] = f"正在清洗QA对 ({processed_count}/{total_pairs})"

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_qa_pair, qa) for qa in qa_pairs]
        concurrent.futures.wait(futures)

    return cleaned_qa

# 将QA对保存到Excel
def save_to_excel(qa_pairs, output_file):
    if not qa_pairs:
        df = pd.DataFrame(columns=['work_order_id', 'question', 'answer'])
    else:
        df = pd.DataFrame(qa_pairs)
        # 确保所有列存在
        for col in ['work_order_id', 'question', 'answer']:
            if col not in df.columns:
                df[col] = None
    df.to_excel(output_file, index=False)
    logging.info(f"已将QA对保存到 {output_file}")

# 处理任务的后台函数
def process_task(task_id, file_path, api_key):
    if not api_key:
        api_key = os.getenv('DASHSCOPE_API_KEY')
        if not api_key:
            task_status[task_id]['status'] = "缺少API密钥"
            task_status[task_id]['progress'] = 100
            return
    try:
        task_status[task_id]['status'] = "开始读取Excel文件..."
        task_status[task_id]['progress'] = 0
        
        # 读取Excel
        df = read_excel(file_path)
        if df is None:
            task_status[task_id]['status'] = "读取Excel文件失败"
            task_status[task_id]['progress'] = 100
            return
        
        task_status[task_id]['status'] = "正在分组工单数据..."
        task_status[task_id]['progress'] = 10
        
        # 按工单ID分组
        work_orders = group_by_work_order(df)
        
        task_status[task_id]['status'] = f"共有 {len(work_orders)} 个工单，开始格式化对话..."
        task_status[task_id]['progress'] = 20
        formatted_texts = format_conversations(api_key, work_orders, task_id)
        
        task_status[task_id]['status'] = f"格式化完成，开始生成QA对..."
        task_status[task_id]['progress'] = 50
        
        # 生成QA对
        qa_pairs = generate_qa_pairs(api_key, formatted_texts, task_id)
        
        task_status[task_id]['status'] = "开始清洗QA对..."
        task_status[task_id]['progress'] = 50
        
        # 清洗QA对
        cleaned_qa = clean_qa_pairs(api_key, qa_pairs, task_id)
        
        task_status[task_id]['status'] = "正在保存结果..."
        task_status[task_id]['progress'] = 90
        
        # 保存结果
        output_file = os.path.join(RESULT_FOLDER, f"{task_id}_cleaned_qa_pairs.xlsx")
        save_to_excel(cleaned_qa, output_file)
        
        # 更新任务状态
        task_status[task_id]['status'] = f"处理完成！共生成 {len(cleaned_qa)} 个清洗后QA对"
        task_status[task_id]['progress'] = 100
        task_status[task_id]['result_file'] = output_file
        task_status[task_id]['qa_count'] = len(cleaned_qa)
        task_status[task_id]['cleaned_qa'] = cleaned_qa  # 临时存储以供显示
        
    except Exception as e:
        logging.error(f"处理任务出错: {e}")
        task_status[task_id]['status'] = f"处理过程中发生错误: {str(e)}"
        task_status[task_id]['progress'] = 100

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('没有文件部分')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('未选择任何文件')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            api_key = request.form.get('api_key')
            if not api_key:
                flash('API密钥是必需的。')
                return redirect(request.url)
            task_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
        file.save(file_path)
        task_status[task_id] = {
            'status': '任务已创建',
            'progress': 0,
            'result_file': None,
            'qa_count': 0
            }
        thread = threading.Thread(target=process_task, args=(task_id, file_path, api_key))
        thread.daemon = True
        thread.start()
        return redirect(url_for('show_status', task_id=task_id))
    return render_template('index.html')

@app.route('/status_page/<task_id>')
def show_status(task_id):
    return render_template('status.html', task_id=task_id)



@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/upload', methods=['POST'])
def upload_file_new():
    if 'file' not in request.files:
        return jsonify({'error': '没有选择文件'}), 400
    
    file = request.files['file']
    api_key = request.form.get('api_key', '').strip()
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if not api_key:
        return jsonify({'error': '请输入API密钥'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': '只支持Excel文件格式 (.xlsx, .xls)'}), 400
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 保存上传的文件
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
    file.save(file_path)
    
    # 初始化任务状态
    task_status[task_id] = {
        'status': '任务已创建',
        'progress': 0,
        'result_file': None,
        'qa_count': 0
    }
    
    # 在后台线程中处理任务
    thread = threading.Thread(target=process_task, args=(task_id, file_path, api_key))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'message': '文件上传成功，开始处理...'
    })

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(task_status[task_id])

@app.route('/download/<task_id>')
def download_result(task_id):
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404
    
    task = task_status[task_id]
    if not task.get('result_file') or not os.path.exists(task['result_file']):
        return jsonify({'error': '结果文件不存在'}), 404
    
    return send_file(
        task['result_file'],
        as_attachment=True,
        download_name=f"qa_pairs_{task_id}.xlsx"
    )

@app.route('/result/<task_id>', methods=['GET'])
def show_cleaned_result(task_id):
    if task_id not in task_status:
        flash('任务不存在')
        return redirect(url_for('upload_file'))
    task = task_status[task_id]
    if 'cleaned_qa' not in task:
        flash('清洗结果不可用')
        return redirect(url_for('upload_file'))
    qa_data = task['cleaned_qa']
    return render_template('result.html', qa_data=qa_data, task_id=task_id)

@app.route('/submit_selection/<task_id>', methods=['POST'])
def submit_selection(task_id):
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404
    selected_indices = request.form.getlist('selected')
    cleaned_qa = task_status[task_id]['cleaned_qa']
    final_qa = [cleaned_qa[int(idx)] for idx in selected_indices if idx.isdigit()]
    final_file = os.path.join(RESULT_FOLDER, f"{task_id}_final_qa_pairs.xlsx")
    save_to_excel(final_qa, final_file)
    task_status[task_id]['final_file'] = final_file
    return jsonify({'message': '筛选完成', 'download_url': url_for('download_final', task_id=task_id)})

@app.route('/download_final/<task_id>')
def download_final(task_id):
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404
    task = task_status[task_id]
    if 'final_file' not in task or not os.path.exists(task['final_file']):
        return jsonify({'error': '最终文件不存在'}), 404
    return send_file(task['final_file'], as_attachment=True, download_name=f"final_qa_pairs_{task_id}.xlsx")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Vercel无服务器适配
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['RESULT_FOLDER'] = '/tmp/results'

# 确保模板目录路径正确（Vercel环境）
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app.template_folder = template_dir

# 确保临时目录存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['RESULT_FOLDER']):
    os.makedirs(app.config['RESULT_FOLDER'])

# Vercel入口点
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # 生产环境配置
    app.config['DEBUG'] = False