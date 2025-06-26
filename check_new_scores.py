import json
import time
import requests
from bs4 import BeautifulSoup
import os
from colorama import init, Fore, Style
try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

# 初始化colorama
init()

# 配置参数
OUTPUT_DIR = "data"  # 输出目录
MAX_RETRIES = 3  # 最大重试次数
TIMEOUT = (5, 10)  # 连接和读取超时（秒）

# 绩点映射
GRADE_TO_GPA = {
    (95, 100): 5.0, (92, 94): 4.8, (89, 91): 4.5, (86, 88): 4.2,
    (83, 85): 3.9, (80, 82): 3.6, (77, 79): 3.3, (74, 76): 3.0,
    (71, 73): 2.7, (68, 70): 2.4, (65, 67): 2.1, (62, 64): 1.8,
    (60, 61): 1.5, (0, 59): 0.0
}

# RSA加密函数，用于加密登录密码
def _rsa_encrypt(password_str, e_str, M_str):
    """使用RSA算法加密密码"""
    password_bytes = bytes(password_str, 'ascii')
    password_int = int.from_bytes(password_bytes, 'big')
    e_int = int(e_str, 16)
    M_int = int(M_str, 16)
    result_int = pow(password_int, e_int, M_int)
    return hex(result_int)[2:].rjust(128, '0')

# 创建输出目录
def ensure_output_dir():
    """创建输出目录（如果不存在）"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

# 保存数据到JSON文件
def save_to_file(data, filename):
    """将数据保存到JSON文件"""
    ensure_output_dir()
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 学期映射函数
def map_semester(semester_code):
    """将网站爬取的学期代码映射为 '23-24秋冬' 格式"""
    if not semester_code or not isinstance(semester_code, str) or len(semester_code) < 12:
        return "未知学期"
    try:
        semester_part = semester_code[1:].split(')')[0]
        start_year, end_year, term = semester_part.split('-')
        short_start = str(int(start_year) % 100).zfill(2)
        short_end = str(int(end_year) % 100).zfill(2)
        return f"{short_start}-{short_end}秋冬" if term == "1" else f"{short_start}-{short_end}春夏"
    except Exception:
        return "未知学期"

# 转换五级制成绩
def convert_grade(score_text):
    """将五级制成绩转换为百分制和绩点"""
    grade_map = {
        "优秀": (90.0, 4.5),
        "良好": (80.0, 3.5),
        "中等": (70.0, 2.5),
        "及格": (60.0, 1.5),
        "不及格": (0.0, 0.0)
    }
    if score_text in grade_map:
        return grade_map[score_text]
    try:
        score = float(score_text)
        for (low, high), gpa in GRADE_TO_GPA.items():
            if low <= score <= high:
                return score, gpa
        return score, 0.0
    except ValueError:
        return 0.0, 0.0

# 计算均绩和均分
def calculate_metrics(courses):
    """计算均绩、主修均绩、百分制均分、主修百分制均分"""
    total_weight = 0.0
    total_gpa = 0.0
    total_score = 0.0
    major_weight = 0.0
    major_gpa = 0.0
    major_score = 0.0

    for course in courses:
        score, gpa = convert_grade(course['cj'] if 'cj' in course else course['score'])
        credits = float(course['xf'] if 'xf' in course else course['credits'])
        weight = credits * (1.0 if course['is_major'] else 0.3)
        total_weight += weight
        total_gpa += gpa * weight
        total_score += score * weight
        if course['is_major']:
            major_weight += credits
            major_gpa += gpa * credits
            major_score += score * credits

    gpa = total_gpa / total_weight if total_weight > 0 else 0.0
    avg_score = total_score / total_weight if total_weight > 0 else 0.0
    major_gpa = major_gpa / major_weight if major_weight > 0 else 0.0
    major_avg_score = major_score / major_weight if major_weight > 0 else 0.0

    return {
        'gpa': round(gpa, 4),
        'avg_score': round(avg_score, 4),
        'major_gpa': round(major_gpa, 4),
        'major_avg_score': round(major_avg_score, 4)
    }

# 爬取成绩单和专业课程统计数据
def fetch_data(username, password):
    """爬取成绩单和专业课程统计数据"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }

    data_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Host': 'zdbk.zju.edu.cn',
        'Origin': 'https://zdbk.zju.edu.cn',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive'
    }

    session = requests.session()
    session.headers.update(headers)

    log_url = 'https://zjuam.zju.edu.cn/cas/login?service=https%3A%2F%2Fzdbk.zju.edu.cn%2Fjwglxt%2Fxtgl%2Flogin_ssologin.html'

    user_data = {'username': username, 'password': password, 'execution': None, '_eventId': 'submit'}
    for attempt in range(MAX_RETRIES):
        try:
            res = session.get(log_url, timeout=TIMEOUT)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            input_tag = soup.find('input', {'name': 'execution'})
            if not input_tag:
                return [], False
            user_data['execution'] = input_tag['value']
            break
        except requests.exceptions.RequestException:
            if attempt == MAX_RETRIES - 1:
                return [], False
            time.sleep(1)

    try:
        res = session.get('https://zjuam.zju.edu.cn/cas/v2/getPubKey', timeout=TIMEOUT).json()
        n, e = res['modulus'], res['exponent']
        user_data['password'] = _rsa_encrypt(password, e, n)
    except Exception:
        return [], False

    try:
        login_response = session.post(log_url, data=user_data, allow_redirects=False, timeout=TIMEOUT)
        if login_response.status_code not in [200, 301, 302]:
            return [], False

        current_url = login_response.headers.get('location')
        if current_url:
            if current_url.startswith("http://"):
                current_url = current_url.replace("http://", "https://")
            max_redirects = 10
            redirect_count = 0
            while current_url and redirect_count < max_redirects:
                try:
                    redirect_response = session.get(current_url, allow_redirects=False, timeout=TIMEOUT)
                    redirect_response.raise_for_status()
                    if 'filtererr.jsp' in current_url:
                        return [], False
                    current_url = redirect_response.headers.get('location')
                    if current_url and current_url.startswith("http://"):
                        current_url = current_url.replace("http://", "https://")
                    redirect_count += 1
                except requests.exceptions.RequestException:
                    return [], False
    except Exception:
        return [], False

    # 验证JSESSIONID和route
    j_session_id = next((c for c in session.cookies if c.name == 'JSESSIONID' and c.path == '/jwglxt'), None)
    route = next((c for c in session.cookies if c.name == 'route'), None)
    if not j_session_id or not route:
        return [], False

    score_url = f'https://zdbk.zju.edu.cn/jwglxt/cxdy/xscjcx_cxXscjIndex.html?doType=query&queryModel.showCount=2000'
    score_data = []
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(score_url, headers=data_headers, timeout=TIMEOUT)
            if response.status_code != 200:
                return [], False
            try:
                data = response.json()
                score_data = data.get('items', [])
                break
            except ValueError:
                return [], False
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return [], False
            time.sleep(1)

    stats_url = f'https://zdbk.zju.edu.cn/jwglxt/zycjtj/xszgkc_cxXsZgkcIndex.html?doType=query&queryModel.showCount=2000'
    stats_data = []
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(stats_url, headers=data_headers, timeout=TIMEOUT)
            if response.status_code != 200:
                return [], False
            try:
                data = response.json()
                stats_data = [item for item in data.get('items', []) if item.get('xdbjmc') != '未修']
                break
            except ValueError:
                return [], False
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return [], False
            time.sleep(1)

    courses = []
    existing_courses = set()
    
    for item in stats_data:
        course_name = item.get('kcmc', '')
        if course_name and item.get('cj', ''):
            semester = map_semester(item.get('xkkh', ''))
            credits = float(item.get('xf', 0.0))
            course_key = (course_name, credits, semester)
            courses.append({
                'name': course_name,
                'credits': credits,
                'score': item.get('cj', ''),
                'semester': semester,
                'is_major': True
            })
            existing_courses.add(course_key)

    for item in score_data:
        course_name = item.get('kcmc', '')
        if course_name and item.get('cj', '') and (course_name, float(item.get('xf', 0.0)), map_semester(item.get('xkkh', ''))) not in existing_courses:
            semester = map_semester(item.get('xkkh', ''))
            credits = float(item.get('xf', 0.0))
            courses.append({
                'name': course_name,
                'credits': credits,
                'score': item.get('cj', ''),
                'semester': semester,
                'is_major': False
            })

    return courses, True

def main():
    """主函数，循环检测新成绩"""
    while True:
        username = input("请输入学号：")
        password = input("请输入密码：")
        
        # 尝试登录并验证
        courses, success = fetch_data(username, password)
        if success and (len(courses) > 0 or j_session_id and route):  # 确保有课程数据或会话有效
            print("登录成功！")
            break
        print("登录失败，请检查学号和密码后重试")
    
    # 获取检测间隔
    while True:
        try:
            interval = int(input("请输入检测间隔（秒，10-3600）："))
            if 10 <= interval <= 3600:
                break
            print("间隔必须在10到3600秒之间，请重新输入")
        except ValueError:
            print("请输入有效的整数")
    
    # 存储上一次的课程列表
    previous_courses = []
    first_run = True
    
    while True:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 爬取数据
        courses, success = fetch_data(username, password)
        
        if not success:
            print(f"{current_time}: 数据获取失败，将在{interval}秒后重试")
            time.sleep(interval)
            continue
        
        if first_run:
            print(f"{current_time}: 首次检测，获取到 {len(courses)} 门课程：")
            for i, course in enumerate(courses, 1):
                print(f"{i}. 课程名: {course['name']}, 学分: {course['credits']}, 成绩: {course['score']}, 学期: {course['semester']}")
            metrics = calculate_metrics(courses)
            print(f"{Fore.YELLOW}均绩: {metrics['gpa']:.4f}, 百分制均分: {metrics['avg_score']:.4f}, 主修均绩: {metrics['major_gpa']:.4f}, 主修百分制均分: {metrics['major_avg_score']:.4f}{Style.RESET_ALL}")
            previous_courses = [(c['name'], c['credits'], c['semester']) for c in courses]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_to_file(courses, f"courses_{timestamp}.json")
            first_run = False
        else:
            # 比较新旧课程
            current_courses = [(c['name'], c['credits'], c['semester']) for c in courses]
            new_courses = [c for c in courses if (c['name'], c['credits'], c['semester']) not in previous_courses]
            
            if new_courses:
                new_course_names = [c['name'] for c in new_courses]
                print(f"{Fore.RED}{current_time}: 有新科目出分：{new_course_names}{Style.RESET_ALL}")
                if PLYER_AVAILABLE:
                    notification.notify(
                        title="新成绩通知",
                        message=f"有新科目出分：{', '.join(new_course_names)}",
                        timeout=10
                    )
                else:
                    while True:
                        print(f"{Fore.RED}{current_time}: 有新科目出分：{new_course_names}（请输入1确认收到）{Style.RESET_ALL}")
                        user_input = input()
                        if user_input == '1':
                            break
                        time.sleep(1)
                
                metrics = calculate_metrics(courses)
                print(f"{Fore.YELLOW}均绩: {metrics['gpa']:.4f}, 百分制均分: {metrics['avg_score']:.4f}, 主修均绩: {metrics['major_gpa']:.4f}, 主修百分制均分: {metrics['major_avg_score']:.4f}{Style.RESET_ALL}")
                previous_courses = current_courses
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_to_file(courses, f"courses_{timestamp}.json")
            else:
                print(f"{current_time}: 无新课程出分")
        
        time.sleep(interval)

if __name__ == '__main__':
    main()