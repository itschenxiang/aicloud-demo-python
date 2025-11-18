import base64
import hashlib
import time
import uuid
import requests
import os

# === 请填写你自己的本地文件地址 ===
LOCAL_FILE_PATH = '请填写你自己的本地文件地址'

# === 请填写你自己的应用ID和密钥 ===
APP_KEY = "你的应用ID"
APP_SECRET = "你的应用密钥"

# === 高级版 API 基础URL ===
BASE_URL = "https://openapi.youdao.com/file_convert/v2"
UPLOAD_URL = f"{BASE_URL}/upload"
QUERY_URL = f"{BASE_URL}/query"

def truncate(q: str) -> str:
    """根据文档规则生成 input 字符串"""
    if len(q) <= 20:
        return q
    return q[:10] + str(len(q)) + q[-10:]


def sha256_digest(s: str) -> str:
    """生成 SHA256 签名"""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def gen_sign(q_or_flownumber: str) -> tuple:
    """生成签名所需参数：salt, curtime, sign"""
    salt = str(uuid.uuid4())
    curtime = str(int(time.time()))
    input_str = truncate(q_or_flownumber)
    sign_str = APP_KEY + input_str + salt + curtime + APP_SECRET
    sign = sha256_digest(sign_str)
    return salt, curtime, sign


def upload_pdf(file_path: str, target_type="docx"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    with open(file_path, "rb") as f:
        file_base64 = base64.b64encode(f.read()).decode("utf-8")

    salt, curtime, sign = gen_sign(file_base64)

    # 注意 multipart/form-data 传参方式
    form_data = {
        "appKey": (None, APP_KEY),
        "salt": (None, salt),
        "curtime": (None, curtime),
        "sign": (None, sign),
        "signType": (None, "v3"),
        "q": (None, file_base64),
        "fileName": (None, os.path.basename(file_path)),
        "fileType": (None, "pdf"),
        "targetFileType": (None, target_type),
    }

    print("正在以 multipart/form-data 上传文件...")
    resp = requests.post(UPLOAD_URL, files=form_data, timeout=120)
    print(f"HTTP状态: {resp.status_code}")
    print(resp.text)

    result = resp.json()
    if result.get("code") == "0" and result.get("data"):
        flownumber = result["data"]["flownumber"]
        print(f"上传成功，任务流水号: {flownumber}")
        return flownumber
    else:
        raise Exception(f"上传失败: {result}")


def query_task(flownumber: str):
    """查询任务状态（multipart/form-data 方式）"""
    salt, curtime, sign = gen_sign(flownumber)

    form_data = {
        "appKey": (None, APP_KEY),
        "salt": (None, salt),
        "curtime": (None, curtime),
        "sign": (None, sign),
        "signType": (None, "v3"),
        "flownumber": (None, flownumber),
    }

    print(f"查询任务状态: {flownumber}")
    resp = requests.post(QUERY_URL, files=form_data, timeout=30)
    print(f"HTTP状态: {resp.status_code}")
    print(resp.text)

    try:
        result = resp.json()
    except Exception:
        raise Exception(f"返回结果无法解析为JSON: {resp.text}")

    if result.get("code") != "0":
        raise Exception(f"查询失败: {result}")
    return result


def wait_for_result(flownumber: str, interval=5, timeout=300):
    """轮询任务状态直到完成或失败"""
    print("查询任务进度中...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        result = query_task(flownumber)
        data = result.get("data", {})
        status = data.get("status")
        status_str = data.get("statusString", "")
        print(f"任务状态: {status} ({status_str})")

        if status == 4:
            url = data.get("resultUrl")
            print(f"转换完成，下载地址: {url}")
            return url
        elif status == -2:
            raise Exception("转换失败")
        time.sleep(interval)
    raise TimeoutError("任务超时未完成")


def download_result(result_url: str, save_path: str):
    """下载转换后的结果文件"""
    print("正在下载结果...")
    resp = requests.get(result_url)
    with open(save_path, "wb") as f:
        f.write(resp.content)
    print(f"文件已保存到: {save_path}")


if __name__ == "__main__":
    # === 示例使用 ===
    # 输出的Word文件名
    output_file = "result.docx"

    flownumber = upload_pdf(LOCAL_FILE_PATH, target_type="docx")
    result_url = wait_for_result(flownumber)
    # 保存文件到本地
    download_result(result_url, output_file)
