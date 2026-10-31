import requests

class IchancyAPI:
    def __init__(self, base_url="https://your-ichancy-domain.com"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None

    def signin(self, username, password):
        """تسجيل الدخول للحصول على Access & Refresh Tokens"""
        url = f"{self.base_url}/global/api/UserApi/signin"
        payload = {"username": username, "password": password}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status"):
                self.access_token = data.get("accessToken")
                self.refresh_token = data.get("refreshToken")
                return True, "تم تسجيل الدخول بنجاح"
        
        return False, response.json().get("notification", [{"content": "خطأ في تسجيل الدخول"}])[0]["content"]

    def refresh_access_token(self):
        """تجديد التوكن المنتهي"""
        url = f"{self.base_url}/global/api/UserApi/refreshToken"
        payload = {"refreshToken": self.refresh_token}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status"):
                self.access_token = data.get("accessToken")
                self.refresh_token = data.get("refreshToken")
                return True
        return False

    def _make_request(self, endpoint, payload):
        """دالة مساعدة لإرسال الطلبات مع إعادة محاولة التجديد تلقائياً"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = requests.post(url, json=payload, headers=headers)
        
        # إذا انتهى التوكن (Unauthorized)، نقوم بتجديده وإعادة المحاولة مرة واحدة
        if response.status_code == 201 or response.status_code == 403:
            if self.refresh_access_token():
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = requests.post(url, json=payload, headers=headers)
                
        return response.json()

    def get_agent_wallets(self):
        """جلب معلومات المحافظ والرصيد للوكيل"""
        return self._make_request("/global/api/UserApi/getAgentAllWallets", {})

    def register_player(self, username, email, password, parent_id):
        """تسجيل لاعب جديد تحت الوكيل"""
        payload = {
            "player": {
                "email": email,
                "password": password,
                "parentId": parent_id,
                "login": username
            }
        }
        return self._make_request("/global/api/UserApi/registerPlayer", payload)

    def deposit_to_player(self, player_id, amount, comment=""):
        """إيداع رصيد للاعب"""
        payload = {
            "amount": float(amount),
            "comment": comment,
            "playerld": player_id,
            "currencyCode": "NSP",
            "currency": "NSP",
            "moneyStatus": 5
        }
        return self._make_request("/global/api/UserApi/depositToPlayer", payload)

    def withdraw_from_player(self, player_id, amount, comment=""):
        """سحب رصيد من اللاعب (القيمة تكون بالسالب حسب التوثيق)"""
        payload = {
            "amount": -abs(float(amount)), 
            "comment": comment,
            "playerld": player_id,
            "currencyCode": "NSP",
            "currency": "NSP",
            "moneyStatus": 5
        }
        return self._make_request("/global/api/UserApi/withdrawFromPlayer", payload)
