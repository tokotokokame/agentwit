class BypassDetector:
    PROXY_HEADER = "X-Agentwit-Proxy"
    PROXY_VALUE  = "1"

    def inject_header(self, headers: dict) -> dict:
        """プロキシがリクエストに付与するヘッダー"""
        headers[self.PROXY_HEADER] = self.PROXY_VALUE
        return headers

    def check_request(self, headers: dict) -> dict | None:
        """
        プロキシヘッダーがない場合はバイパスの可能性を返す。
        正常時はNone、バイパス疑いは dict を返す。
        """
        if self.PROXY_HEADER not in headers:
            return {
                "type":     "proxy_bypass_detected",
                "severity": "HIGH",
                "detail":   "Request missing X-Agentwit-Proxy header"
            }
        return None
