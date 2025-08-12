import pandas as pd
import requests
import json
import time
from openpyxl import Workbook
from collections import defaultdict
from tqdm import tqdm

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
        user_name = row['oa_user_name'] if not pd.isna(row['oa_user_name']) else '系统'
        
        # 跳过空内容
        if pd.isna(content) or content.strip() == '':
            continue
            
        work_orders[work_id].append({
            'user': user_name,
            'content': content
        })
    
    return work_orders

# 调用百炼API生成QA对
def generate_qa_pairs(api_key, conversations, model_name):
    qa_pairs = []
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 添加进度条
    pbar = tqdm(conversations.items(), desc="调用API生成QA对")
    for work_id, messages in pbar:
        # 更新进度条描述，显示当前处理的工单ID
        pbar.set_description(f"处理工单 {work_id}")
        
        # 构建对话内容
        conversation_text = "\n".join([f"{msg['user']}: {msg['content']}" for msg in messages])
        
        # 构建提示词
        prompt = f"""你是一个工单问答提取助手。你的任务是根据以下工单对话内容,理解并抽取出核心问题和对应的解决方案或回答。请确保提取的答案是完整且准确的,并且只包含与问题直接相关的信息。如果对话中没有明确的答案,请说明。请以JSON格式输出结果。如果存在多个问答对,请输出一个JSON数组。

对话内容：
{conversation_text}

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
        
        # 构建请求体
        payload = {
            "model": model_name,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的问答提取助手，擅长从对话中提取出问题和答案对。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            "parameters": {}
        }
        
        # 添加重试机制
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 设置超时时间
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                # 解析API返回的结果
                if 'output' in result and 'text' in result['output']:
                    response_text = result['output']['text']
                    
                    # 尝试解析JSON
                    try:
                        # 查找JSON部分
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
                        print(f"解析工单 {work_id} 的JSON结果时出错: {e}")
                        print(f"原始响应: {response_text}")
                
                # 成功处理，跳出重试循环
                break
                
            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"工单 {work_id} 请求超时，正在进行第 {retry_count} 次重试...")
                    time.sleep(2)  # 重试前等待时间增加
                else:
                    print(f"工单 {work_id} 请求超时，已达到最大重试次数")
            
            except requests.exceptions.RequestException as e:
                print(f"调用API处理工单 {work_id} 时出错: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"正在进行第 {retry_count} 次重试...")
                    time.sleep(2)
                else:
                    print(f"已达到最大重试次数，跳过此工单")
            
            except KeyboardInterrupt:
                print("\n用户中断操作，正在保存已处理的结果...")
                return qa_pairs
            
            except Exception as e:
                print(f"处理工单 {work_id} 时发生未知错误: {e}")
                break
        
        # 避免API限流
        time.sleep(1)
    
    return qa_pairs

# 将QA对保存到Excel
def save_to_excel(qa_pairs, output_file):
    wb = Workbook()
    ws = wb.active
    ws.title = "QA Pairs"
    
    # 添加表头
    ws.append(["工单ID", "问题", "回答"])
    
    # 添加数据
    for qa in tqdm(qa_pairs, desc="保存QA对到Excel"):
        ws.append([qa['work_order_id'], qa['question'], qa['answer']])
    
    # 调整列宽
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 50
    ws.column_dimensions['C'].width = 80
    
    # 保存文件
    wb.save(output_file)
    print(f"已将QA对保存到 {output_file}")

# 处理文件的核心逻辑
def process_file(input_file, output_file, api_key, model_name):
    print("开始处理工单数据...")
    
    try:
        # 读取Excel
        df = read_excel(input_file)
        if df is None:
            return
        
        print(f"成功读取Excel，共 {len(df)} 条记录")
        
        # 按工单ID分组
        work_orders = group_by_work_order(df)
        print(f"共有 {len(work_orders)} 个不同的工单")
        
        # 生成QA对
        print("开始调用API生成QA对...")
        qa_pairs = generate_qa_pairs(api_key, work_orders, model_name)
        print(f"成功生成 {len(qa_pairs)} 个QA对")
        
        # 保存结果
        save_to_excel(qa_pairs, output_file)
        
    except KeyboardInterrupt:
        print("\n用户中断操作，程序退出")
    except Exception as e:
        print(f"程序执行过程中发生错误: {e}")
        raise e
    finally:
        print("程序执行完毕")

# 主函数
def main():
    input_file = "e:\\工作\\QA-match\\order_chat.xlsx"
    output_file = "e:\\工作\\QA-match\\qa_pairs.xlsx"
    api_key = "sk-af3b28d2f51b41b8bfa56ed8305ac9d4"  # 警告：请勿在代码中硬编码API密钥
    
    process_file(input_file, output_file, api_key)

if __name__ == "__main__":
    main()