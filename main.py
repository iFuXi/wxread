# main.py 主逻辑：包括字段拼接、模拟请求
import os
import time
import random
import hashlib
import logging
import urllib.parse
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)-8s - %(message)s'
)
logger = logging.getLogger(__name__)

class WeReadBot:
    def __init__(self):
        self.config = self._load_config()
        self.cookies = self.config['cookies']
        self.headers = self.config['headers']
        self.key = self.config['key']
        self.read_num = self.config['read_num']
        self.push_method = self.config['push_method']

    def _load_config(self):
        """从环境变量加载配置"""
        return {
            'key': os.getenv('WXREAD_KEY'),
            'cookies': json.loads(os.getenv('WXREAD_COOKIES')),
            'headers': json.loads(os.getenv('WXREAD_HEADERS')),
            'read_num': int(os.getenv('WXREAD_READ_NUM')),
            'push_method': os.getenv('WXREAD_PUSH_METHOD')
        }

    def encode_data(self, data):
        """数据编码"""
        return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_wr_skey(self):
        """安全刷新cookie密钥"""
        response = requests.post(
            'https://weread.qq.com/web/login/renewal',
            headers=self.headers,
            cookies=self.cookies,
            json={"rq": "%2Fweb%2Fbook%2Fread"}
        )
        response.raise_for_status()
        for cookie in response.headers.get('Set-Cookie', '').split(';'):
            if "wr_skey" in cookie:
                return cookie.split('=')[-1][:8]
        raise ValueError("无法获取新密钥")

    def run(self):
        base_data = {
            'ct': int(time.time()),
            'rn': random.randint(0, 1000),
            'key': self.key
        }
        for index in range(1, self.read_num + 1):
            try:
                # 生成动态参数
                data = {
                    **base_data,
                    'ts': int(time.time() * 1000),
                    'sg': hashlib.sha256(f"{base_data['ts']}{base_data['rn']}{base_data['key']}".encode()).hexdigest(),
                    's': self.cal_hash(self.encode_data(base_data))
                }
                
                # 发送请求
                response = self._safe_post(data)
                if response.get('succ'):
                    logger.info(f"✅ 阅读成功（{index}/{self.read_num}）")
                    time.sleep(random.uniform(25, 35))  # 随机延迟
                else:
                    logger.warning("❌ 请求失败，正在重试...")
            except Exception as e:
                logger.error(f"❌ 发生错误: {str(e)}")
                self._handle_error()
        self._send_notification()

    def _safe_post(self, data):
        """安全的POST请求"""
        response = requests.post(
            'https://weread.qq.com/web/book/read',
            headers=self.headers,
            cookies=self.cookies,
            json=data
        )
        response.raise_for_status()
        return response.json()

    def _handle_error(self):
        """错误处理逻辑"""
        try:
            new_skey = self.get_wr_skey()
            self.cookies['wr_skey'] = new_skey
            logger.info(f"🔄 密钥刷新成功: {new_skey}")
        except Exception as e:
            logger.error(f"❌ 无法恢复: {str(e)}")
            self._send_notification(f"任务失败: {str(e)}")
            raise

    def _send_notification(self, message=None):
        """发送通知"""
        if not self.push_method:
            return
        message = message or f"🎉 阅读完成！累计时长：{self.read_num * 0.5}分钟"
        # 实现具体推送逻辑...

if __name__ == "__main__":
    bot = WeReadBot()
    bot.run()
